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

def square_wave_step_plot(all_tasks, resource, capacity, x_min, x_max):
    df = all_tasks[all_tasks['Resource'] == resource].sort_values('Start date')
    changes = []
    for _, row in df.iterrows():
        changes.append((row['Start date'], 1))
        changes.append((row['End date'], -1))
    changes.sort()
    times, usage, current = [], [], 0
    for t, delta in changes:
        times.append(t)
        usage.append(current)
        current += delta
        times.append(t)
        usage.append(current)
    # Add x-axis padding for full timescale
    if times and (times[0] > x_min):
        times = [x_min] + times
        usage = [0] + usage
    if times and (times[-1] < x_max):
        times.append(x_max)
        usage.append(usage[-1])
    step_df = pd.DataFrame({'time': times, 'usage': usage})
    step_df['conflict'] = step_df['usage'] > capacity
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=step_df['time'], y=step_df['usage'],
        mode='lines',
        name=f'{resource} Usage',
        line=dict(shape='hv', color='blue', width=3)
    ))
    fig.add_trace(go.Scatter(
        x=step_df['time'][step_df['conflict']],
        y=step_df['usage'][step_df['conflict']],
        mode='markers',
        name='Conflict',
        marker=dict(color='red', size=12)
    ))
    fig.update_layout(
        title=f"Step Plot - {resource} (Square Wave)",
        xaxis=dict(title="Time", range=[x_min, x_max]),
        yaxis=dict(title="Usage", tickvals=[0,1,2,3], range=[0,3]),
        showlegend=True,
        height=350
    )
    return fig

# --- Streamlit App State ---
if "all_tasks" not in st.session_state:
    st.session_state.all_tasks = pd.DataFrame(columns=['Title', 'Start date', 'End date', 'Resource'])
if "hide_tasks" not in st.session_state:
    st.session_state.hide_tasks = set()
if "hide_resources" not in st.session_state:
    st.session_state.hide_resources = set()
if "resource_caps" not in st.session_state:
    st.session_state.resource_caps = {}
if "hide_step_plots" not in st.session_state:
    st.session_state.hide_step_plots = set()

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
