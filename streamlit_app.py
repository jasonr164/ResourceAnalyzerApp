import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def parse_gantt_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    required_cols = ['Title', 'Start date', 'End date']
    if not all(col in df.columns for col in required_cols):
        st.error(f"File {uploaded_file.name} missing columns: {required_cols}")
        return pd.DataFrame(columns=required_cols)
    return df[required_cols]

def excel_date(num):
    return pd.Timestamp('1899-12-30') + pd.to_timedelta(num, unit='D')

# Streamlit App State
if "all_tasks" not in st.session_state:
    st.session_state.all_tasks = pd.DataFrame(columns=['Title', 'Start date', 'End date', 'Resource'])
if "hide_tasks" not in st.session_state:
    st.session_state.hide_tasks = set()
if "hide_resources" not in st.session_state:
    st.session_state.hide_resources = set()
if "resource_caps" not in st.session_state:
    st.session_state.resource_caps = {}

# File uploader
st.title("Resource Gantt Comparison Tool")

uploaded_files = st.file_uploader(
    "Upload Gantt chart files (CSV or Excel)",
    type=['csv', 'xls', 'xlsx'], accept_multiple_files=True
)

if uploaded_files:
    # Only parse/upload if newly uploaded
    fresh_tasks = pd.DataFrame(columns=['Title', 'Start date', 'End date', 'Resource'])
    for file in uploaded_files:
        df = parse_gantt_file(file)
        # Assign initial Resource as Title
        df['Resource'] = df['Title']
        fresh_tasks = pd.concat([fresh_tasks, df], ignore_index=True)
    # Convert numeric to date if needed
    for col in ['Start date', 'End date']:
        if np.issubdtype(fresh_tasks[col].dtype, np.number):
            fresh_tasks[col] = fresh_tasks[col].apply(excel_date)
        else:
            fresh_tasks[col] = pd.to_datetime(fresh_tasks[col])
    # Reset app state (only on new upload)
    st.session_state.all_tasks = fresh_tasks
    st.session_state.hide_tasks = set()
    st.session_state.hide_resources = set()
    st.session_state.resource_caps = {}

tasks = st.session_state.all_tasks.copy()

# --- Task editor / Hide ---
st.subheader("Tasks Loaded")
if not tasks.empty:
    hide_task_indices = st.session_state.hide_tasks if "hide_tasks" in st.session_state else set()
    task_rows = []
    for idx, row in tasks.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2,2,2,2,1])
        col1.write(row['Title'])
        col2.write(row['Start date'])
        col3.write(row['End date'])
        # Resource edit dropdown
        resource_list = sorted(set(tasks['Resource'].unique()).union(tasks['Title'].unique()))
        new_resource = col4.selectbox(
            "Resource", resource_list, index=resource_list.index(row['Resource']),
            key=f"resource_select_{idx}"
        )
        tasks.at[idx, 'Resource'] = new_resource
        st.session_state.all_tasks.at[idx, 'Resource'] = new_resource
        hide = col5.checkbox("Hide", value=(idx in hide_task_indices), key=f"hide_{idx}")
        if hide:
            st.session_state.hide_tasks.add(idx)
        else:
            st.session_state.hide_tasks.discard(idx)
    display_tasks = tasks[~tasks.index.isin(st.session_state.hide_tasks)]
else:
    display_tasks = tasks

# Persistent Step Plot Hide
if "hide_step_plots" not in st.session_state:
    st.session_state.hide_step_plots = set()

for resource in sorted(final_tasks['Resource'].unique()):
    hide_this_step = st.checkbox(
        f"Hide Step Plot for {resource}",
        value=(resource in st.session_state.hide_step_plots),
        key=f"hide_step_{resource}"
    )
    if hide_this_step:
        st.session_state.hide_step_plots.add(resource)
    else:
        st.session_state.hide_step_plots.discard(resource)
    if resource not in st.session_state.hide_step_plots:
        # (Plotting code for this step plot)

"""
# Resource capacity controls with delete/hide option
st.subheader("Resource Capacity Settings")
resource_caps = st.session_state.resource_caps
edit_resources = sorted(display_tasks['Resource'].unique())
for resource in edit_resources:
    cap_col, hide_col = st.columns([3, 1])
    if resource not in resource_caps:
        resource_caps[resource] = 1
    cap = cap_col.number_input(f"Capacity for {resource}", min_value=1, value=resource_caps[resource], key=f"cap_{resource}")
    resource_caps[resource] = cap
    if hide_col.checkbox(f"Hide", value=False, key=f"hide_resource_{resource}"):
        st.session_state.hide_resources.add(resource)
    else:
        if resource in st.session_state.hide_resources:
            st.session_state.hide_resources.remove(resource)
"""

# Only show tasks for visible resources
final_tasks = display_tasks[~display_tasks['Resource'].isin(st.session_state.hide_resources)]

if st.button("Analyze"):
    st.subheader("Combined Gantt Chart")
    if not final_tasks.empty:
        fig = px.timeline(
            final_tasks,
            x_start="Start date", x_end="End date", y="Resource", color="Title",
            title="Combined Gantt Chart"
        )
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

        # X-axis range for all step plots
        gantt_x0 = final_tasks['Start date'].min()
        gantt_x1 = final_tasks['End date'].max()
        st.subheader("Step Plot Visualizations")

        # Step plots for each resource
        for resource in sorted(final_tasks['Resource'].unique()):
            if resource in st.session_state.hide_resources:
                continue
            df_res = final_tasks[final_tasks['Resource'] == resource].sort_values('Start date')
            changes = []
            for _, row in df_res.iterrows():
                changes.append((row['Start date'], 1))
                changes.append((row['End date'], -1))
            changes.sort()
            # Build square wave data
            times, usage, current = [], [], 0
            for t, delta in changes:
                times.append(t)
                usage.append(current)
                current += delta
                times.append(t)
                usage.append(current)
            # Add ends for xlim if necessary
            if times and (times[0] > gantt_x0):
                times = [gantt_x0] + times
                usage = [0] + usage
            if times and (times[-1] < gantt_x1):
                times.append(gantt_x1)
                usage.append(usage[-1])
            # Step DataFrame for plotting
            step_df = pd.DataFrame({'time': times, 'usage': usage})
            step_df['conflict'] = step_df['usage'] > resource_caps[resource]
            fig_step = go.Figure()
            fig_step.add_trace(go.Scatter(
                x=step_df['time'], y=step_df['usage'],
                mode='lines',
                name=f'{resource} Usage',
                line=dict(shape='hv', color='blue', width=3)
            ))
            # Red marker for conflict
            fig_step.add_trace(go.Scatter(
                x=step_df['time'][step_df['conflict']],
                y=step_df['usage'][step_df['conflict']],
                mode='markers',
                name='Conflict',
                marker=dict(color='red', size=12)
            ))
            fig_step.update_layout(
                title=f"Step Plot - {resource} (Square Wave)",
                xaxis=dict(title="Time", range=[gantt_x0, gantt_x1]),
                yaxis=dict(title="Usage", tickvals=[0,1,2,3], range=[0,3]),
                showlegend=True,
                height=350
            )
            hide_this_step = st.checkbox(f"Hide Step Plot for {resource}", value=False, key=f"hide_step_{resource}")
            if not hide_this_step:
                st.plotly_chart(fig_step, use_container_width=True)

        st.subheader("Export Results")
        st.write("Right-click on any plot to save as PNG.")
    else:
        st.info("No tasks/resources to display. All have been hidden or deleted.")

else:
    st.info("Upload at least one CSV or Excel file to begin and press Analyze.")

st.markdown("---")
st.caption("Upload files, flexibly assign resources, edit/hide/delete, analyze, and visualize resource conflicts.")
