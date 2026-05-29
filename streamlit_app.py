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
