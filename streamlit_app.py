import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

def parse_gantt_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    # Ensure columns match your file exactly
    required_cols = ['Title', 'Start date', 'End date']
    if not all(col in df.columns for col in required_cols):
        st.error(f"File {uploaded_file.name} missing columns: {required_cols}")
        return pd.DataFrame(columns=required_cols)
    return df[required_cols]

def combined_gantt_chart(all_tasks):
    fig = px.timeline(
        all_tasks,
        x_start="Start date", x_end="End date", y="Resource", color="Title",
        title="Combined Gantt Chart"
    )
    fig.update_yaxes(autorange="reversed")
    return fig

def compute_step_plot(all_tasks, resource, capacity):
    df = all_tasks[all_tasks['Resource'] == resource].sort_values('Start date')
    changes = []
    for _, row in df.iterrows():
        changes.append((row['Start date'], 1))  # Step up
        changes.append((row['End date'], -1))   # Step down

    changes.sort()
    times = []
    usage = []
    current = 0

    for i, (t, delta) in enumerate(changes):
        times.append(t)
        usage.append(current)
        current += delta
        times.append(t)
        usage.append(current)

    # Remove duplicate times (optional for cleaner chart)
    step_data = pd.DataFrame({'time': times, 'usage': usage})
    step_data = step_data.sort_values('time')

    # Identify conflicts
    step_data['conflict'] = step_data['usage'] > capacity

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=step_data['time'], y=step_data['usage'],
        mode='lines',
        name=f'{resource} Usage',
        line=dict(shape='hv', color='blue', width=3)
    ))
    # Conflict highlight
    fig.add_trace(go.Scatter(
        x=step_data['time'][step_data['conflict']],
        y=step_data['usage'][step_data['conflict']],
        mode='markers',
        name='Conflict',
        marker=dict(color='red', size=12)
    ))
    fig.update_layout(
        title=f"Step Plot - {resource} (Square Wave)",
        xaxis_title="Time", yaxis_title="Usage",
        showlegend=True
    )
    return fig
    
st.title("Resource Gantt Comparison Tool")

uploaded_files = st.file_uploader(
    "Upload Gantt chart files (CSV or Excel)",
    type=['csv', 'xls', 'xlsx'], accept_multiple_files=True
)

all_tasks = pd.DataFrame(columns=['Title', 'Start date', 'End date', 'Resource'])

if uploaded_files:
    for file in uploaded_files:
        df = parse_gantt_file(file)
        # Assign Resource as Title
        df['Resource'] = df['Title']
        all_tasks = pd.concat([all_tasks, df], ignore_index=True)

    # Convert start/end dates from Excel numeric to datetime if needed
    # Handles integer/float Excel serial numbers
    def excel_date(num):
        return pd.Timestamp('1899-12-30') + pd.to_timedelta(num, unit='D')
    for col in ['Start date', 'End date']:
        if np.issubdtype(all_tasks[col].dtype, np.number):
            all_tasks[col] = all_tasks[col].apply(excel_date)
        else:
            all_tasks[col] = pd.to_datetime(all_tasks[col])

    st.subheader("Tasks Loaded")
    st.dataframe(all_tasks[['Title', 'Start date', 'End date', 'Resource']])

    st.subheader("Resource Capacity Settings")
    resource_caps = {}
    for resource in all_tasks['Resource'].unique():
        resource_caps[resource] = st.number_input(
            f"Capacity for {resource}", value=1, min_value=1
        )

    if st.button("Analyze"):
        st.subheader("Combined Gantt Chart")
        st.plotly_chart(combined_gantt_chart(all_tasks), use_container_width=True)

        st.subheader("Step Plot Visualizations")
        for resource in all_tasks['Resource'].unique():
            fig = compute_step_plot(all_tasks, resource, resource_caps[resource])
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Export Results")
        st.write("Right-click on any plot to save as PNG.")

else:
    st.info("Upload at least one CSV or Excel file to begin.")

st.markdown("---")
st.caption("Upload files, edit capacities, analyze, and visualize resource conflicts.")
