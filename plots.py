from datetime import timedelta

import plotly.graph_objects as go

from sqm import SQM


def make_sqm_plot(df):
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(x=df["local_datetime"], y=df[SQM.MSAS], yaxis="y", name="MSAS")
    )

    if "moon_phase" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["local_datetime"],
                y=df["moon_phase"],
                yaxis="y2",
                name="Moon Phase",
            )
        )

    if "moon_elevation" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["local_datetime"],
                y=df["moon_elevation"],
                yaxis="y3",
                name="Moon Elevation",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[df["local_datetime"].min(), df["local_datetime"].max()],
                y=[0, 0],
                yaxis="y3",
                name="Horizon",
            )
        )

    # Set title
    fig.update_layout(title_text="SQM Metrics", showlegend=False)

    # Add range slider
    date_max = max(df["local_datetime"])
    date_min = max(date_max - timedelta(days=30), min(df["local_datetime"]))
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list(
                    [
                        dict(count=1, label="day", step="day", stepmode="backward"),
                        dict(count=1, label="month", step="month", stepmode="backward"),
                        dict(count=1, label="year", step="year", stepmode="backward"),
                        dict(step="all"),
                    ]
                )
            ),
            rangeslider=dict(visible=True),
            range=[date_min, date_max],
            type="date",
        ),
        yaxis=dict(
            anchor="x",
            autorange=True,
            domain=[0, 0.333],
            linecolor="#673ab7",
            mirror=True,
            range=[0, 24],
            showline=True,
            side="right",
            title="MSAS",
            zeroline=False,
        ),
        yaxis2=dict(
            anchor="x",
            autorange=True,
            domain=[0.334, 0.666],
            linecolor="#795548",
            mirror=True,
            range=[0, 1],
            showline=True,
            side="right",
            title="Moon Phase",
            zeroline=False,
        ),
        yaxis3=dict(
            anchor="x",
            autorange=True,
            domain=[0.667, 1],
            linecolor="#2196F3",
            mirror=True,
            range=[0, 360],
            showline=True,
            side="right",
            title="Moon Elevation",
            zeroline=True,
        ),
        height=700,
    )

    # Shade day as yellow and night as dark blue
    if "group" in df.columns:
        NIGHT_COLOR = "rgba(64, 64, 255, 0.2)"
        DAY_COLOR = "rgba(255, 200, 32, 0.2)"
        shapes = []
        gb = df.groupby("group")
        group_starts = gb["local_datetime"].min()
        group_ends = gb["local_datetime"].max()
        for group in gb.groups:
            x0, x1 = group_starts[group], group_ends[group]
            color = NIGHT_COLOR if "night" in group else DAY_COLOR
            shapes.append(
                dict(
                    fillcolor=color,
                    line={"width": 0},
                    type="rect",
                    x0=x0,
                    x1=x1,
                    y0=0,
                    y1=1,
                    yref="paper",
                )
            )
        fig.update_layout(shapes=shapes)

    print(fig)
    return fig
