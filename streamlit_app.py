import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# -----------------------------
# File parsing
# -----------------------------
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

# -----------------------------
# Step plot (IMPROVED)
# -----------------------------
def square_wave_step_plot(all_tasks, resource, capacity, x_min, x_max):
    df = all_tasks[all_tasks['Resource'] == resource].sort_values('Start date')

    changes = []
    for _, row in df.iterrows():
        changes.append((row['Start date'], 1))
        changes.append((row['End date'], -1))

    changes.sort()

    times, usage = [], []
    current = 0

    for t, delta in changes:
        times.append(t)
        usage.append(current)
        current += delta
        times.append(t)
        usage.append(current)

    if not times:
        return go.Figure()

    # Extend range
    if times[0] > x_min:
        times.insert(0, x_min)
        usage.insert(0, 0)

    if times[-1] < x_max:
        times.append(x_max)
        usage.append(usage[-1])

    step_df = pd.DataFrame({'time': times, 'usage': usage})

    fig = go.Figure()

    # Main square wave
    fig.add_trace(go.Scatter(
        x=step_df['time'],
        y=step_df['usage'],
        mode='lines',
        line=dict(shape='hv', width=3),
        name=f"{resource} Usage"
    ))

    # Conflict shading
    over = step_df['usage'] > capacity
    fig.add_trace(go.Scatter(
        x=step_df['time'],
        y=np.where(over, step_df['usage'], capacity),
        fill='tonexty',
        mode='lines',
        line=dict(width=0),
        fillcolor='rgba(255,0,0,0.3)',
        name="Over Capacity"
    ))

    # Capacity line
    fig.add_hline(y=capacity, line_dash="dash", line_color="red")

    # ✅ Whole-number Y axis only
    y_max = int(max(step_df['usage'].max(), capacity))
    fig.update_layout(
        title=f"{resource} Utilization",
        xaxis=dict(range=[x_min, x_max]),
        yaxis=dict(
            title="Usage",
            tickmode='linear',
            dtick=1,   # ← forces whole numbers
            range=[0, y_max + 1]
        ),
        height=350
    )

    return fig

# -----------------------------
# Session State
# -----------------------------
if "all_tasks" not in st.session_state:
    st.session_state.all_tasks = pd.DataFrame(
        columns=['Title', 'Start date', 'End date', 'Resource']
    )
if "hide_tasks" not in st.session_state:
    st.session_state.hide_tasks = set()
if "resource_caps" not in st.session_state:
    st.session_state.resource_caps = {}
if "hide_step_plots" not in st.session_state:
    st.session_state.hide_step_plots = set()

# -----------------------------
# App UI
# -----------------------------
st.title("Resource Gantt Comparison Tool")

uploaded_files = st.file_uploader(
    "Upload Gantt chart files",
    type=['csv', 'xls', 'xlsx'],
    accept_multiple_files=True
)

if uploaded_files:
    fresh_tasks = pd.DataFrame(columns=['Title', 'Start date', 'End date', 'Resource'])

    for file in uploaded_files:
        df = parse_gantt_file(file)
        df['Resource'] = df['Title']
        fresh_tasks = pd.concat([fresh_tasks, df], ignore_index=True)

    # Date parsing
    for col in ['Start date', 'End date']:
        if np.issubdtype(fresh_tasks[col].dtype, np.number):
            fresh_tasks[col] = fresh_tasks[col].apply(excel_date)
        else:
            fresh_tasks[col] = pd.to_datetime(fresh_tasks[col], errors='coerce')

    fresh_tasks = fresh_tasks.dropna(subset=['Start date', 'End date'])

    # ✅ Append instead of overwrite
    st.session_state.all_tasks = pd.concat(
        [st.session_state.all_tasks, fresh_tasks],
        ignore_index=True
    ).drop_duplicates()

tasks = st.session_state.all_tasks.copy()

# -----------------------------
# ✅ Tasks table (compact UI)
# -----------------------------
st.subheader("Tasks Loaded")

if not tasks.empty:
    display_df = tasks.copy()

    display_df['Hide'] = display_df.index.isin(st.session_state.hide_tasks)

    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Title": st.column_config.TextColumn(),
            "Start date": st.column_config.DatetimeColumn(),
            "End date": st.column_config.DatetimeColumn(),
            "Resource": st.column_config.SelectboxColumn(
                options=sorted(tasks['Resource'].unique())
            ),
            "Hide": st.column_config.CheckboxColumn()
        }
    )

    # Apply edits
    st.session_state.all_tasks[['Title', 'Start date', 'End date', 'Resource']] = \
        edited_df[['Title', 'Start date', 'End date', 'Resource']]

    # Update hidden rows
    st.session_state.hide_tasks = set(
        edited_df[edited_df['Hide']].index
    )

    display_tasks = edited_df[~edited_df['Hide']]
else:
    display_tasks = tasks

# -----------------------------
# ✅ Resource Capacity (cleaned)
# -----------------------------
st.subheader("Resource Capacity Settings")

resource_caps = st.session_state.resource_caps

resources = sorted(display_tasks['Resource'].unique())

# Compact layout
cols = st.columns(min(3, len(resources)) if resources else 1)

for i, resource in enumerate(resources):
    col = cols[i % len(cols)]

    if resource not in resource_caps:
        resource_caps[resource] = 1

    resource_caps[resource] = col.number_input(
        resource,
        min_value=1,
        value=resource_caps[resource],
        key=f"cap_{resource}"
    )

final_tasks = display_tasks.copy()

# -----------------------------
# Analyze button
# -----------------------------
if st.button("Analyze"):
    st.session_state.analyzed = True

if st.session_state.get("analyzed", False):

    st.subheader("Combined Gantt Chart")

    if not final_tasks.empty:
        fig = px.timeline(
            final_tasks,
            x_start="Start date",
            x_end="End date",
            y="Resource",
            color="Resource",
            hover_data=["Title"]
        )

        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)

        gantt_x0 = final_tasks['Start date'].min()
        gantt_x1 = final_tasks['End date'].max()

        # -----------------------------
        # Step plots
        # -----------------------------
        st.subheader("Step Plot Visualizations")

        for resource in resources:
            hide = st.checkbox(
                f"Hide Step Plot for {resource}",
                value=(resource in st.session_state.hide_step_plots),
                key=f"hide_step_{resource}"
            )

            if hide:
                st.session_state.hide_step_plots.add(resource)
            else:
                st.session_state.hide_step_plots.discard(resource)

            if resource not in st.session_state.hide_step_plots:
                fig_step = square_wave_step_plot(
                    final_tasks,
                    resource,
                    resource_caps[resource],
                    gantt_x0,
                    gantt_x1
                )
                st.plotly_chart(fig_step, use_container_width=True)

        # -----------------------------
        # ✅ Conflict Summary
        # -----------------------------
        st.subheader("Conflict Summary")

        conflicts = []

        for resource in resources:
            df = final_tasks[final_tasks['Resource'] == resource]

            events = []
            for _, row in df.iterrows():
                events.append((row['Start date'], 1))
                events.append((row['End date'], -1))

            events.sort()

            current = 0
            for t, delta in events:
                current += delta
                if current > resource_caps[resource]:
                    conflicts.append((resource, t, current))

        if conflicts:
            st.dataframe(
                pd.DataFrame(conflicts, columns=["Resource", "Time", "Usage"])
            )
        else:
            st.success("No conflicts detected ✅")

    else:
        st.info("No tasks to display.")

else:
    st.info("Upload files and click Analyze.")

st.markdown("---")
st.caption("Upload, edit, assign resources, and analyze conflicts.")

