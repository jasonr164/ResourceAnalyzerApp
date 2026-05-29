import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# -----------------------------
# Utilities
# -----------------------------
def parse_gantt_file(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    required_cols = ['Title', 'Start date', 'End date']
    if not all(col in df.columns for col in required_cols):
        st.error(f"{uploaded_file.name} missing required columns")
        return pd.DataFrame(columns=required_cols)

    return df[required_cols]

def excel_date(num):
    return pd.Timestamp('1899-12-30') + pd.to_timedelta(num, unit='D')

# -----------------------------
# Expand multi-resource tasks
# -----------------------------
def expand_resources(df):
    rows = []
    for _, r in df.iterrows():
        resources = [x.strip() for x in str(r["Resource"]).split(",")]
        for res in resources:
            new = r.copy()
            new["Resource"] = res
            rows.append(new)
    return pd.DataFrame(rows)

# -----------------------------
# Step plot (with cooldown)
# -----------------------------
def square_wave_step_plot(all_tasks, resource, capacity, cooldown_weeks, x_min, x_max):
    df = all_tasks[all_tasks["Resource"] == resource]

    events = []

    for _, r in df.iterrows():
        start = r["Start date"]
        end = r["End date"]

        # normal usage
        events.append((start, 1))
        events.append((end, -1))

        # cooldown usage
        cooldown_end = end + pd.Timedelta(weeks=cooldown_weeks)
        events.append((end, 0.5))
        events.append((cooldown_end, -0.5))

    events.sort()

    times, usage = [], []
    current = 0

    for t, delta in events:
        times.append(t)
        usage.append(current)
        current += delta
        times.append(t)
        usage.append(current)

    if not times:
        return go.Figure()

    if times[0] > x_min:
        times.insert(0, x_min)
        usage.insert(0, 0)

    if times[-1] < x_max:
        times.append(x_max)
        usage.append(usage[-1])

    step_df = pd.DataFrame({"time": times, "usage": usage})

    fig = go.Figure()

    # Base usage
    fig.add_trace(go.Scatter(
        x=step_df["time"],
        y=step_df["usage"],
        mode="lines",
        line=dict(shape="hv", width=3, color="blue"),
        name="Usage"
    ))

    # Conflict highlighting
    mask = step_df["usage"] > capacity

    fig.add_trace(go.Scatter(
        x=step_df["time"][mask],
        y=step_df["usage"][mask],
        mode="lines",
        line=dict(shape="hv", width=4, color="red"),
        name="Conflict"
    ))

    fig.add_hline(y=capacity, line_dash="dash", line_color="red")

    y_max = int(np.ceil(max(step_df["usage"].max(), capacity)))

    fig.update_layout(
        title=f"{resource}",
        xaxis=dict(range=[x_min, x_max]),
        yaxis=dict(
            tickmode="linear",
            dtick=1,
            range=[0, y_max + 1]
        ),
        height=300
    )

    return fig

# -----------------------------
# Conflict scoring (sorting)
# -----------------------------
def compute_conflict_score(df, capacity):
    events = []
    for _, r in df.iterrows():
        events.append((r["Start date"], 1))
        events.append((r["End date"], -1))

    events.sort()
    current = 0
    score = 0

    for _, delta in events:
        current += delta
        if current > capacity:
            score += (current - capacity)

    return score

# -----------------------------
# Session State
# -----------------------------
if "all_tasks" not in st.session_state:
    st.session_state.all_tasks = pd.DataFrame(
        columns=["Title", "Start date", "End date", "Resource"]
    )

if "hide_tasks" not in st.session_state:
    st.session_state.hide_tasks = set()

if "resource_settings" not in st.session_state:
    st.session_state.resource_settings = {}

# -----------------------------
# App UI
# -----------------------------
st.title("Resource Gantt Tool - Version C1")

uploaded_files = st.file_uploader(
    "Upload files",
    type=["csv", "xls", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    new_tasks = pd.DataFrame()

    for f in uploaded_files:
        df = parse_gantt_file(f)
        df["Resource"] = df["Title"]
        new_tasks = pd.concat([new_tasks, df])

    for col in ["Start date", "End date"]:
        if np.issubdtype(new_tasks[col].dtype, np.number):
            new_tasks[col] = new_tasks[col].apply(excel_date)
        else:
            new_tasks[col] = pd.to_datetime(new_tasks[col], errors="coerce")

    new_tasks = new_tasks.dropna()

    st.session_state.all_tasks = pd.concat(
        [st.session_state.all_tasks, new_tasks],
        ignore_index=True
    )

tasks = st.session_state.all_tasks.copy()

# -----------------------------
# Tasks Table
# -----------------------------
st.subheader("Tasks Loaded")

if not tasks.empty:

    if "edit_buffer" not in st.session_state:
        st.session_state.edit_buffer = tasks.copy()
        st.session_state.edit_buffer["Hide"] = False

    edited = st.data_editor(
        st.session_state.edit_buffer,
        use_container_width=True,
        height=400,
        key="editor"
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ Apply Changes"):
            st.session_state.all_tasks = edited.drop(columns=["Hide"])
            st.session_state.hide_tasks = set(edited[edited["Hide"]].index)
            st.session_state.edit_buffer = edited.copy()

    with col2:
        if st.button("↩ Reset Edits"):
            st.session_state.edit_buffer = tasks.copy()
            st.session_state.edit_buffer["Hide"] = False

    display_tasks = edited[~edited["Hide"]]

else:
    display_tasks = tasks

# -----------------------------
# Expand multi-resource
# -----------------------------
expanded_tasks = expand_resources(display_tasks)

# -----------------------------
# Resource Settings
# -----------------------------
st.subheader("Resource Settings")

resources = sorted(expanded_tasks["Resource"].unique())

cols = st.columns(3)

for i, r in enumerate(resources):
    col = cols[i % 3]

    if r not in st.session_state.resource_settings:
        st.session_state.resource_settings[r] = {
            "capacity": 1,
            "cooldown": 1.0
        }

    settings = st.session_state.resource_settings[r]

    settings["capacity"] = col.number_input(
        f"{r} Capacity",
        min_value=1,
        value=int(settings["capacity"]),
        key=f"cap_{r}"
    )

    settings["cooldown"] = col.number_input(
        f"{r} Cooldown (weeks)",
        min_value=0.0,
        value=float(settings["cooldown"]),
        step=0.5,
        key=f"cool_{r}"
    )

# -----------------------------
# Analyze
# -----------------------------
if st.button("Analyze"):
    st.session_state.analyzed = True

if st.session_state.get("analyzed", False) and not expanded_tasks.empty:

    # -----------------------------
    # Gantt Chart
    # -----------------------------
    st.subheader("Combined Gantt")

    resource_order = (
        expanded_tasks.groupby("Resource")["Start date"]
        .min()
        .sort_values()
        .index.tolist()
    )

    expanded_tasks["Resource"] = pd.Categorical(
        expanded_tasks["Resource"],
        categories=resource_order,
        ordered=True
    )

    expanded_tasks = expanded_tasks.sort_values(["Resource", "Start date"])

    fig = px.timeline(
        expanded_tasks,
        x_start="Start date",
        x_end="End date",
        y="Resource",
        color="Resource",
        hover_data=["Title"]
    )

    fig.update_yaxes(
        categoryorder="array",
        categoryarray=resource_order,
        autorange="reversed"
    )

    st.plotly_chart(fig, width="stretch")

    # -----------------------------
    # Conflict-aware sorting
    # -----------------------------
    scores = {}

    for r in resources:
        df = expanded_tasks[expanded_tasks["Resource"] == r]
        cap = st.session_state.resource_settings[r]["capacity"]
        scores[r] = compute_conflict_score(df, cap)

    sorted_resources = sorted(resources, key=lambda x: scores[x], reverse=True)

    # -----------------------------
    # Step Plots
    # -----------------------------
    st.subheader("Step Plots (Conflict Prioritized)")

    x0 = expanded_tasks["Start date"].min()
    x1 = expanded_tasks["End date"].max()

    for r in sorted_resources:
        settings = st.session_state.resource_settings[r]

        fig = square_wave_step_plot(
            expanded_tasks,
            r,
            settings["capacity"],
            settings["cooldown"],
            x0,
            x1
        )

        st.plotly_chart(fig, width="stretch")
