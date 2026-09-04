import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import re

# ==================================================
# CONFIGURATION
# ==================================================

TASK_FILE = "Tasks.csv"
STATUS_FILE = "task_status.csv"

st.set_page_config(
    page_title="FP&A Readiness Dashboard",
    layout="wide"
)

# ==================================================
# SORTING OF "WHEN"
# ==================================================

def sort_when(value):
    value = str(value).strip()

    if value.upper() == "DAILY":
        return -999

    match = re.match(r"D([+-])(\d+)", value)

    if match:
        sign = match.group(1)
        number = int(match.group(2))
        return -number if sign == "-" else number

    return 999


# ==================================================
# LOAD TASKS
# ==================================================

df = pd.read_csv(TASK_FILE, sep=";")

df.columns = df.columns.str.strip()

for col in df.columns:
    df[col] = df[col].fillna("").astype(str).str.strip()

# Unique Task ID
df["TaskID"] = (
    df["Process"]
    + "|"
    + df["Task"]
    + "|"
    + df["Location"]
)

# ==================================================
# LOAD + MERGE STATUS FILE
# ==================================================

if Path(STATUS_FILE).exists():
    status_df = pd.read_csv(STATUS_FILE)
else:
    status_df = pd.DataFrame(
        columns=["TaskID", "Completed"]
    )

current_tasks = pd.DataFrame({
    "TaskID": df["TaskID"]
})

merged_status = current_tasks.merge(
    status_df,
    on="TaskID",
    how="left"
)

merged_status["Completed"] = (
    merged_status["Completed"]
    .fillna(False)
    .astype(bool)
)

merged_status.to_csv(
    STATUS_FILE,
    index=False
)

status_map = dict(
    zip(
        merged_status["TaskID"],
        merged_status["Completed"]
    )
)

# ==================================================
# SESSION STATE INITIALIZATION
# ==================================================

if "task_status" not in st.session_state:
    st.session_state.task_status = status_map.copy()

# Initialize checkbox widgets
for task_id, completed in status_map.items():

    if task_id not in st.session_state:
        st.session_state[task_id] = completed

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.title("Filters")

# ----------------------
# Process Filter
# ----------------------

processes = sorted(
    df["Process"]
    .dropna()
    .unique()
)

selected_process = st.sidebar.selectbox(
    "Process",
    ["All"] + list(processes)
)

# ----------------------
# Location Filter
# ----------------------

if selected_process == "All":
    location_df = df.copy()
else:
    location_df = df[
        df["Process"] == selected_process
    ]

locations = sorted(
    location_df["Location"]
    .dropna()
    .unique()
)

selected_location = st.sidebar.selectbox(
    "Location",
    ["All"] + list(locations)
)

# ----------------------
# Owner Filter
# ----------------------

owner_df = location_df.copy()

if selected_location != "All":
    owner_df = owner_df[
        owner_df["Location"] == selected_location
    ]

owners = sorted(
    owner_df["Owner"]
    .dropna()
    .unique()
)

selected_owner = st.sidebar.selectbox(
    "Owner",
    ["All"] + list(owners)
)

# ==================================================
# RESET SECTION
# ==================================================

st.sidebar.markdown("---")

confirm_reset = st.sidebar.checkbox(
    "Confirm reset"
)

if st.sidebar.button("Reset All Tasks"):

    if not confirm_reset:

        st.sidebar.error(
            "Please tick 'Confirm reset' first."
        )

    else:

        # Reset dictionary
        for task_id in list(
            st.session_state.task_status.keys()
        ):
            st.session_state.task_status[task_id] = False

        # Reset checkbox widgets
        for task_id in df["TaskID"]:
            st.session_state[task_id] = False

        # Rewrite status file
        reset_df = pd.DataFrame({
            "TaskID": df["TaskID"],
            "Completed": False
        })

        reset_df.to_csv(
            STATUS_FILE,
            index=False
        )

        st.rerun()

# ==================================================
# HEADER
# ==================================================

st.title("📊 FP&A Readiness Dashboard")

# ==================================================
# FILTER DATA
# ==================================================

display_df = df.copy()

if selected_process != "All":
    display_df = display_df[
        display_df["Process"] == selected_process
    ]

if selected_location != "All":
    display_df = display_df[
        display_df["Location"] == selected_location
    ]

if selected_owner != "All":
    display_df = display_df[
        display_df["Owner"] == selected_owner
    ]

display_df = display_df.copy()

display_df["SortWhen"] = (
    display_df["When"]
    .apply(sort_when)
)

display_df = display_df.sort_values(
    by=[
        "SortWhen",
        "Process",
        "Task"
    ]
)

# ==================================================
# CHECKLIST
# ==================================================

st.subheader("✅ Task Checklist")

for milestone, group in display_df.groupby(
    "When",
    sort=False
):

    st.markdown(f"### 📅 {milestone}")

    for _, row in group.iterrows():

        label = (
            f"{row['Task']} "
            f"| {row['Owner']} "
            f"| {row['Location']}"
        )

        checked = st.checkbox(
            label,
            key=row["TaskID"]
        )

        st.session_state.task_status[
            row["TaskID"]
        ] = checked

# ==================================================
# SAVE STATUS
# ==================================================

save_df = pd.DataFrame({
    "TaskID": list(
        st.session_state.task_status.keys()
    ),
    "Completed": list(
        st.session_state.task_status.values()
    )
})

save_df.to_csv(
    STATUS_FILE,
    index=False
)

# ==================================================
# APPLY STATUS
# ==================================================

df["Completed"] = (
    df["TaskID"]
    .map(st.session_state.task_status)
)

# ==================================================
# OVERALL READINESS
# ==================================================

overall_progress = df["Completed"].mean()

st.subheader("📈 Overall Readiness")

col1, col2 = st.columns([1, 4])

with col1:
    st.metric(
        "Completion",
        f"{overall_progress:.0%}"
    )

with col2:
    st.progress(
        float(overall_progress)
    )

# ==================================================
# PROCESS SUMMARY
# ==================================================

process_status = (
    df.groupby("Process")
      .agg(
          Completed=("Completed", "sum"),
          Total=("Completed", "count")
      )
      .reset_index()
)

process_status["Progress"] = (
    process_status["Completed"]
    / process_status["Total"]
    * 100
).round(1)

def rag(value):

    if value >= 90:
        return "🟢"

    if value >= 50:
        return "🟡"

    return "🔴"

process_status["Status"] = (
    process_status["Progress"]
    .apply(rag)
)

st.subheader("🚦 Process Summary")

st.dataframe(
    process_status[
        [
            "Process",
            "Status",
            "Completed",
            "Total",
            "Progress"
        ]
    ],
    use_container_width=True,
    hide_index=True
)

# ==================================================
# CHART
# ==================================================

fig = px.bar(
    process_status,
    x="Progress",
    y="Process",
    orientation="h",
    text="Progress",
    color="Progress",
    color_continuous_scale="RdYlGn"
)

fig.update_traces(
    texttemplate="%{x:.0f}%",
    textposition="outside"
)

fig.update_layout(
    height=500,
    xaxis_title="Completion %",
    yaxis_title="",
    coloraxis_showscale=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# ==================================================
# PENDING ACTIONS
# ==================================================

st.subheader("⏳ Pending Actions")

pending = df[
    df["Completed"] == False
].copy()

pending["SortWhen"] = (
    pending["When"]
    .apply(sort_when)
)

pending = pending.sort_values(
    by=[
        "SortWhen",
        "Process",
        "Task"
    ]
)

if pending.empty:

    st.success(
        "✅ All tasks completed."
    )

else:

    st.dataframe(
        pending[
            [
                "Process",
                "Task",
                "Owner",
                "Location",
                "When",
                "Source"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

# ==================================================
# EXPORT
# ==================================================

st.subheader("💾 Export Current Status")

export_df = df.copy()

csv_export = export_df.to_csv(
    index=False
).encode("utf-8")

st.download_button(
    label="Download Status",
    data=csv_export,
    file_name="readiness_status.csv",
    mime="text/csv"
)

# ==================================================
# STATISTICS
# ==================================================

completed_tasks = int(df["Completed"].sum())
total_tasks = len(df)

st.caption(
    f"Completed {completed_tasks}/{total_tasks} tasks"
)
