import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- Helper Functions ---

def parse_gantt_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    required_cols = ['Title', 'Start Date', 'End date']
    if not all(col in df.columns for col in required_cols):
        st.error(f"File {uploaded_file.name} missing columns: {required_cols}")
        return pd.DataFrame(columns=required_cols)
    return df[required_cols]

def combined_gantt_chart(all_tasks):
    fig = px.timeline(
        all_tasks,
        x_start="Start Date", x_end="End date", y="Resource", color="Title",
        title="Combined Gantt Chart"
    )
    fig.update_yaxes(autorange="reversed")
    return fig

def compute_step_plot(all_tasks, resource, capacity):
    df = all_tasks[all_tasks['Resource'] == resource]
    timeline = []
    for _, row in df.iterrows():
        timeline.append({'time': row['Start Date'], 'change': 1, 'task': row['Title']})
        timeline.append({'time': row['End date'], 'change': -1, 'task': row['Title']})
    timeline = pd.DataFrame(timeline).sort_values(by='time')
    timeline['usage'] = timeline['change'].cumsum()
    timeline['conflict'] = timeline['usage'] > capacity

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline['time'], y=timeline['usage'], mode='lines+markers',
        name=f'{resource} Usage', line=dict(color='blue')
    ))
    if timeline['conflict'].any():
        fig.add_trace(go.Scatter(
            x=timeline['time'][timeline['conflict']],
            y=timeline['usage'][timeline['conflict']],
            mode='markers', name='Conflict',
            marker=dict(color='red', size=12)
        ))
    fig.update_layout(title=f"Step Plot - {resource}",
                     xaxis_title="Time", yaxis_title="Usage")
    return fig

# --- Streamlit App ---

st.title("Resource Gantt Comparison Tool")

uploaded_files = st.file_uploader(
    "Upload Gantt chart files (CSV or Excel)",
    type=['csv', 'xls', 'xlsx'], accept_multiple_files=True
)

all_tasks = pd.DataFrame(columns=['Title', 'Start Date', 'End date', 'Resource'])

if uploaded_files:
    for file in uploaded_files:
        df = parse_gantt_file(file)
        # Assign resource as Title
        df['Resource'] = df['Title']
        all_tasks = pd.concat([all_tasks, df], ignore_index=True)

    # Fix date formats
    all_tasks['Start Date'] = pd.to_datetime(all_tasks['Start Date'])
    all_tasks['End date'] = pd.to_datetime(all_tasks['End date'])

    # Assignment editor (simplified)
    st.subheader("Tasks Loaded")
    st.dataframe(all_tasks[['Title', 'Start Date', 'End date', 'Resource']])

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
