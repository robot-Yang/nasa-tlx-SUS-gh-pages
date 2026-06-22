#!/usr/bin/env python3
"""
Plot NASA TLX box plots for all available tasks, filtered by participant(s).

Usage:
  python3 scripts/plot_tlx_box.py /path/to/file.csv
  python3 scripts/plot_tlx_box.py /path/to/file1.csv /path/to/file2.csv
  python3 scripts/plot_tlx_box.py /path/to/file.csv --person "P01" --tasks "Task 1,Task 2,Task 3"
  python3 scripts/plot_tlx_box.py /path/to/file.csv --person-col "Participant" --person "P01" --person "P02"
"""

from __future__ import print_function

import argparse
from itertools import combinations
import json
import os
import sys

import numpy as np
import pandas as pd

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception:
    tk = None
    filedialog = None
    messagebox = None

import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 15})

try:
    from scipy.stats import wilcoxon
except Exception:
    wilcoxon = None


DEFAULT_CSV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

PERSON_COL_CANDIDATES = [
    "Participant",
    "Participant ID",
    "ParticipantID",
    "Participant Name",
    "Subject",
    "Subject ID",
    "SubjectID",
    "Name",
    "User",
    "User ID",
    "UserID",
    "ID",
]

TASK_COL_CANDIDATES = ["Task", "Task ID", "TaskID"]
NAME_COL_CANDIDATES = ["Name", "Participant Name"]
CAMIPRO_COL_CANDIDATES = [
    "Camipro",
    "Camipro Number",
    "Camipro number",
    "Camipro #",
    "CamiproID",
    "Camipro ID",
]
TASK_NAME_ALIASES = {
    "controller": "joystick",
    "body": "body-motion control",
}

ADDITIONAL_QUESTION_TITLES = {
    "Additional Q1": "Interface Preference",
    "Additional Q2": "Motion Sickness",
    "Additional Q3": "Video Games",
    "Additional Q4": "Teleoperation Experience",
    "Additional Q5": "Feedback",
}
INTERFACE_CHOICE_ORDER = ["Joystick", "Body-motion control"]
# x-axis display labels, matching the trajectory plots (plot 1): horizontal "Joystick" / "Body-control"
AXIS_LABELS = {"joystick": "Joystick", "controller": "Joystick", "body-motion control": "Body-control", "body": "Body-control"}
CHOICE_DISPLAY = {"Joystick": "Joystick", "Body-motion control": "Body-control"}


def axis_label(name):
    return AXIS_LABELS.get(str(name).strip().lower(), str(name))

INTERFACE_CHOICE_KEY_MAP = {
    "joystick": "Joystick",
    "controller": "Joystick",
    "body-motion control": "Body-motion control",
    "body motion control": "Body-motion control",
    "body": "Body-motion control",
    "same": "Same",
}
INTERFACE_CHOICE_QUESTION_SPECS = [
    ("Additional Q1", "Preferred Interface"),
    ("Additional Q2", "More Motion Sickness"),
]
HAPTIC_RANK_COL_CANDIDATES = ["Additional Q4"]
HAPTIC_INFO_ORDER = [
    "Horizontal distribution of swarm",
    "Relative horizontal location of focal drone",
    "Disconnection",
]
HAPTIC_INFO_KEY_MAP = {
    "horizontal distribution of swarm": "Horizontal distribution of swarm",
    "horizontal_distribution": "Horizontal distribution of swarm",
    "relative horizontal location of focal drone": "Relative horizontal location of focal drone",
    "focal_location": "Relative horizontal location of focal drone",
    "disconnection": "Disconnection",
}

BOX_X_START = 1.0
BOX_X_STEP = 0.82
SELECTION_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plot_tlx_box_selection.json")


def task_order_bucket(task_name):
    t = (task_name or "").strip().lower()
    # Keep joystick on the left and body-motion control on the right,
    # consistent with the trajectory-metric plots.
    if "joystick" in t or "controller" in t:
        return -2
    if "body" in t:
        return -1
    if "without haptic" in t or ("fpv" in t and "only" in t):
        return 0
    if "minimap" in t or "mini map" in t or ("fpv" in t and "map" in t):
        return 1
    if "with haptic" in t or ("fpv" in t and "haptic" in t):
        return 2
    return 99


def normalize_task_name(task_name):
    text = str(task_name).strip()
    if not text or text.lower() == "nan":
        return task_name
    return TASK_NAME_ALIASES.get(text.lower(), text)


def normalize_task_column(df, task_col):
    result = df.copy()
    result[task_col] = result[task_col].apply(normalize_task_name)
    return result


def order_tasks_preferred(tasks):
    indexed = list(enumerate(tasks))
    indexed.sort(key=lambda it: (task_order_bucket(it[1]), it[0]))
    return [name for _, name in indexed]


def load_participant_selection_cache():
    if not os.path.isfile(SELECTION_CACHE):
        return set()
    try:
        with open(SELECTION_CACHE, "r") as f:
            data = json.loads(f.read())
    except Exception:
        return set()
    if not isinstance(data, dict):
        return set()
    items = data.get("selected_participants", [])
    if not isinstance(items, list):
        return set()
    return set(normalize_tokens(items))


def save_participant_selection_cache(selected_people):
    try:
        payload = {"selected_participants": list(unique_in_order(normalize_tokens(selected_people)))}
        with open(SELECTION_CACHE, "w") as f:
            f.write(json.dumps(payload, indent=2))
    except Exception:
        return


def pick_csv_files():
    if not tk or not filedialog:
        return []
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        paths = filedialog.askopenfilenames(
            parent=root,
            title="Select NASA TLX CSV export(s)",
            initialdir=DEFAULT_CSV_DIR,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return list(paths)


def latest_csv_in_default_dir():
    if not os.path.isdir(DEFAULT_CSV_DIR):
        return ""

    latest_path = ""
    latest_mtime = -1.0
    for name in os.listdir(DEFAULT_CSV_DIR):
        if not name.lower().endswith(".csv"):
            continue
        full_path = os.path.join(DEFAULT_CSV_DIR, name)
        if not os.path.isfile(full_path):
            continue
        mtime = os.path.getmtime(full_path)
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = full_path
    return latest_path


def read_csv_files(paths):
    frames = []
    for path in paths:
        df = pd.read_csv(path)
        df["Source CSV"] = os.path.basename(path)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True, sort=False)


def find_columns(df, suffix):
    return [col for col in df.columns if col.endswith(suffix)]


def find_prefix_columns(df, prefix):
    return [col for col in df.columns if col.startswith(prefix)]


def compute_tlx(df):
    rating_cols = find_columns(df, " rating")
    weight_cols = find_columns(df, " weight")

    ratings = df[rating_cols].apply(pd.to_numeric, errors="coerce")
    weights = df[weight_cols].apply(pd.to_numeric, errors="coerce")

    if "Product sum" in df.columns and "Weight sum" in df.columns:
        product_sum = pd.to_numeric(df["Product sum"], errors="coerce")
        weight_sum = pd.to_numeric(df["Weight sum"], errors="coerce")
    else:
        product_sum = (ratings * weights).sum(axis=1, min_count=1)
        weight_sum = weights.sum(axis=1, min_count=1)

    weighted_tlx = product_sum / weight_sum
    raw_tlx = ratings.mean(axis=1, skipna=True)

    result = df.copy()
    result["Product_Sum_Computed"] = product_sum
    result["Weight_Sum"] = weight_sum
    result["TLX_Weighted"] = weighted_tlx
    result["TLX_Raw"] = raw_tlx
    result["TLX_Used"] = np.where(weight_sum > 0, weighted_tlx, raw_tlx)
    result["TLX_Source"] = np.where(weight_sum > 0, "weighted", "raw")

    return result


def compute_sus(df):
    result = df.copy()
    sus_cols = ["SUS Q%d" % i for i in range(1, 11) if "SUS Q%d" % i in result.columns]
    if "SUS Score" in result.columns:
        result["SUS_Score"] = pd.to_numeric(result["SUS Score"], errors="coerce")
    else:
        result["SUS_Score"] = np.nan

    if len(sus_cols) == 10:
        answers = result[sus_cols].apply(pd.to_numeric, errors="coerce")
        odd_items = answers.iloc[:, [0, 2, 4, 6, 8]] - 1
        even_items = 5 - answers.iloc[:, [1, 3, 5, 7, 9]]
        complete_rows = answers.notna().all(axis=1)
        computed = (odd_items.sum(axis=1) + even_items.sum(axis=1)) * 2.5
        result.loc[complete_rows, "SUS_Score"] = result.loc[complete_rows, "SUS_Score"].fillna(computed.loc[complete_rows])

    return result


def guess_column(df, candidates):
    for name in candidates:
        if name in df.columns:
            return name
    return ""


def normalize_tokens(values):
    return [str(v).strip() for v in values if str(v).strip() != ""]


def unique_in_order(values):
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def parse_index_tokens(tokens, max_index):
    selected_indices = []
    for token in tokens:
        if "-" in token:
            parts = [part.strip() for part in token.split("-")]
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start = int(parts[0])
                end = int(parts[1])
                if start > end:
                    start, end = end, start
                for i in range(start, end + 1):
                    if 1 <= i <= max_index:
                        selected_indices.append(i)
                continue
        if token.isdigit():
            i = int(token)
            if 1 <= i <= max_index:
                selected_indices.append(i)
    return unique_in_order(selected_indices)


def yes_no_prompt(prompt, default=False):
    suffix = " [Y/n]: " if default else " [y/N]: "
    value = input(prompt + suffix).strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def first_non_empty(series):
    for value in series:
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def build_participant_groups(df, person_col):
    groups = []
    index_lookup = {}
    for idx, value in df[person_col].items():
        person = str(value).strip()
        if not person or person.lower() == "nan":
            continue
        if person not in index_lookup:
            index_lookup[person] = len(groups)
            groups.append({"person": person, "rows": [idx]})
        else:
            groups[index_lookup[person]]["rows"].append(idx)
    return groups


def edit_participant_info(df, person_col):
    name_col = guess_column(df, NAME_COL_CANDIDATES)
    camipro_col = guess_column(df, CAMIPRO_COL_CANDIDATES)
    if not name_col and not camipro_col:
        return df, False

    if not yes_no_prompt("Edit participant Name/Camipro before plotting?", default=False):
        return df, False

    edited = False

    while True:
        groups = build_participant_groups(df, person_col)
        if not groups:
            break

        print("")
        print("Participants:")
        for i, group in enumerate(groups, start=1):
            row_idx = group["rows"]
            display_name = first_non_empty(df.loc[row_idx, name_col]) if name_col else ""
            display_camipro = first_non_empty(df.loc[row_idx, camipro_col]) if camipro_col else ""
            if name_col and camipro_col:
                print("  %d) %s | %s=%s | %s=%s" % (i, group["person"], name_col, display_name, camipro_col, display_camipro))
            elif name_col:
                print("  %d) %s | %s=%s" % (i, group["person"], name_col, display_name))
            else:
                print("  %d) %s | %s=%s" % (i, group["person"], camipro_col, display_camipro))

        raw = input("Select participant number(s) to edit (e.g., 2,4-6), Enter to continue: ").strip()
        if not raw:
            break

        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        indices = parse_index_tokens(tokens, len(groups))
        if not indices:
            print("No valid participant indices selected.")
            continue

        for index in indices:
            group = groups[index - 1]
            row_idx = group["rows"]
            print("")
            print("Editing participant: %s" % group["person"])
            if name_col:
                current = first_non_empty(df.loc[row_idx, name_col])
                new_value = input("  New %s (leave blank to keep '%s'): " % (name_col, current)).strip()
                if new_value:
                    df.loc[row_idx, name_col] = new_value
                    edited = True
            if camipro_col:
                current = first_non_empty(df.loc[row_idx, camipro_col])
                new_value = input("  New %s (leave blank to keep '%s'): " % (camipro_col, current)).strip()
                if new_value:
                    df.loc[row_idx, camipro_col] = new_value
                    edited = True

            # Keep participant selection consistent with edited identity columns.
            if person_col == name_col and name_col:
                df.loc[row_idx, person_col] = first_non_empty(df.loc[row_idx, name_col])
            if person_col == camipro_col and camipro_col:
                df.loc[row_idx, person_col] = first_non_empty(df.loc[row_idx, camipro_col])

    return df, edited


def maybe_save_edited_csv(df, original_path):
    if not yes_no_prompt("Save edited participant data to a new CSV?", default=False):
        return

    if original_path:
        base, ext = os.path.splitext(original_path)
        default_path = base + "_edited" + (ext or ".csv")
    else:
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "combined_edited.csv")
    target_path = input("Output CSV path (Enter for '%s'): " % default_path).strip()
    if not target_path:
        target_path = default_path
    df.to_csv(target_path, index=False)
    print("Saved edited CSV:", target_path)


def plot_questionnaire_box(df, task_col, person_col, tasks, prefix, title):
    cols = find_prefix_columns(df, prefix)
    if not cols:
        return None

    data = []
    labels = []
    values_by_task = {}
    for task in tasks:
        task_rows = df[df[task_col].astype(str) == task]
        if task_rows.empty:
            values = pd.Series([], dtype=float)
            participant_count = 0
        else:
            values = task_rows[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True)
            values.index = task_rows[person_col].astype(str).values
            values = values.dropna().groupby(level=0).mean()
            participant_count = int(task_rows[person_col].astype(str).nunique())
        values_by_task[task] = values
        data.append(values)
        labels.append(axis_label(task))

    if not any(len(values) for values in data):
        return None

    fig, ax = plt.subplots(figsize=(max(5.2, len(labels) * 1.45), 5))
    boxplot_with_labels(ax, data, labels, showmeans=True)
    ax.set_title(title)
    ax.set_ylabel("Rating")
    plt.xticks(rotation=20, ha="right")

    tests = run_wilcoxon_tests(values_by_task)
    annotate_significance(ax, tasks, values_by_task, tests)

    fig.tight_layout()
    return fig


def plot_questionnaire_questions_separately(df, task_col, person_col, tasks, prefix, title_prefix, title_map=None):
    cols = find_prefix_columns(df, prefix)
    if not cols:
        return [], {}

    figures = []
    values_by_column = {}
    for col in cols:
        data = []
        labels = []
        values_by_task = {}
        for task in tasks:
            task_rows = df[df[task_col].astype(str) == task]
            values = index_values_by_participant(task_rows, col, person_col)
            participant_count = int(task_rows[person_col].astype(str).nunique()) if not task_rows.empty else 0
            values_by_task[task] = values
            data.append(values)
            labels.append(axis_label(task))

        if not any(len(values) for values in data):
            continue

        question_title = title_map.get(col, "%s: %s" % (title_prefix, col)) if title_map else "%s: %s" % (title_prefix, col)

        fig, ax = plt.subplots(figsize=(max(5.2, len(labels) * 1.45), 5))
        boxplot_with_labels(ax, data, labels, showmeans=True)
        ax.set_title(question_title)
        ax.set_ylabel("Rating")
        plt.xticks(rotation=20, ha="right")
        annotate_significance(ax, tasks, values_by_task, run_wilcoxon_tests(values_by_task))
        fig.tight_layout()
        figures.append(fig)
        values_by_column[col] = values_by_task

    return figures, values_by_column


def collect_questionnaire_values_by_column(df, task_col, tasks, prefix, person_col=None):
    cols = find_prefix_columns(df, prefix)
    values_by_column = {}
    for col in cols:
        values_by_task = {}
        for task in tasks:
            task_rows = df[df[task_col].astype(str) == task]
            values = index_values_by_participant(task_rows, col, person_col)
            values_by_task[task] = values
        if any(len(values) for values in values_by_task.values()):
            values_by_column[col] = values_by_task
    return values_by_column


def normalize_interface_choice(value):
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    key = " ".join(text.lower().replace("_", " ").split())
    return INTERFACE_CHOICE_KEY_MAP.get(key, "")


def collect_interface_choice_counts(df, col_name):
    if col_name not in df.columns:
        return {}

    counts = {choice: 0 for choice in INTERFACE_CHOICE_ORDER}
    has_values = False
    for value in df[col_name]:
        choice = normalize_interface_choice(value)
        # "Same" responses are not counted for either interface.
        if choice in counts:
            counts[choice] += 1
            has_values = True

    return counts if has_values else {}


def collect_interface_choice_panels(df):
    panels = []
    for col_name, title in INTERFACE_CHOICE_QUESTION_SPECS:
        counts = collect_interface_choice_counts(df, col_name)
        if counts:
            panels.append((title, counts))
    return panels


def print_interface_choice_summary(choice_panels):
    for title, counts in choice_panels:
        print("")
        print("=== Choice Counts: %s ===" % title)
        parts = ["%s=%d" % (choice, counts.get(choice, 0)) for choice in INTERFACE_CHOICE_ORDER]
        print(", ".join(parts))


def draw_metric_boxplot(ax, task_order, labels, values_by_task, title, ylabel):
    data = [values_by_task.get(task, pd.Series([], dtype=float)) for task in task_order]
    if not any(len(values) for values in data):
        ax.set_visible(False)
        return False

    boxplot_with_labels(ax, data, labels, showmeans=True)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=0)
    for label in ax.get_xticklabels():
        label.set_ha("center")
    annotate_significance(ax, task_order, values_by_task, run_wilcoxon_tests(values_by_task))
    return True


def draw_choice_barplot(ax, counts, title):
    if not counts:
        ax.set_visible(False)
        return False

    values = [counts.get(choice, 0) for choice in INTERFACE_CHOICE_ORDER]

    if not any(values):
        ax.set_visible(False)
        return False

    # Match the box positions, width, and x-limits of the NASA-TLX / SUS boxplots
    # so the bars render at the same width as the boxes.
    x = BOX_X_START + BOX_X_STEP * np.arange(len(INTERFACE_CHOICE_ORDER))
    ax.bar(x, values, width=0.5, color="#4c78a8")
    ax.set_title(title)
    ax.set_ylabel("Count")
    ax.set_xticks(x)
    ax.set_xticklabels([CHOICE_DISPLAY[c] for c in INTERFACE_CHOICE_ORDER])
    ax.set_xlim(x[0] - 0.45, x[-1] + 0.45)
    ax.tick_params(axis="x", labelrotation=0)
    for label in ax.get_xticklabels():
        label.set_ha("center")
    return True


def plot_combined_dashboard(task_order, labels, panel_specs, choice_panel_specs=None):
    valid_specs = []
    for title, ylabel, values_by_task in panel_specs:
        if values_by_task and any(len(values_by_task.get(task, [])) for task in task_order):
            valid_specs.append(("metric", title, ylabel, values_by_task))
    for title, counts in (choice_panel_specs or []):
        if counts and any(counts.values()):
            valid_specs.append(("choice", title, "", counts))
    if not valid_specs:
        return None

    n = len(valid_specs)
    rows = 1
    cols = n
    fig, axes = plt.subplots(rows, cols, figsize=(3.6 * cols, 4.4))
    axes = np.atleast_1d(axes).flatten()

    for i, spec in enumerate(valid_specs):
        panel_type, title, ylabel, values_by_task = spec
        if panel_type == "choice":
            draw_choice_barplot(axes[i], values_by_task, title)
        else:
            draw_metric_boxplot(axes[i], task_order, labels, values_by_task, title, ylabel)

    for j in range(len(valid_specs), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("NASA TLX and Questionnaire Summary", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def index_values_by_participant(task_rows, value_col, person_col):
    """Numeric values for value_col, indexed by participant (one mean per participant).

    Indexing by participant lets paired tests align the same person across tasks.
    Falls back to the row index when no participant column is available.
    """
    values = pd.to_numeric(task_rows[value_col], errors="coerce")
    if person_col is not None and person_col in task_rows.columns and not task_rows.empty:
        values.index = task_rows[person_col].astype(str).values
        return values.dropna().groupby(level=0).mean()
    return values.dropna()


def collect_task_values(df, task_col, tasks, value_col, person_col=None):
    values_by_task = {}
    for task in tasks:
        task_rows = df[df[task_col].astype(str) == task]
        values_by_task[task] = index_values_by_participant(task_rows, value_col, person_col)
    return values_by_task


def boxplot_with_labels(ax, data, labels, showmeans=True):
    n = max(1, len(labels))
    # Keep default box widths; reduce center-to-center distance to tighten gaps.
    positions = BOX_X_START + BOX_X_STEP * np.arange(n)
    box = ax.boxplot(data, positions=positions, showmeans=showmeans)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels)
    ax.set_xlim(positions[0] - 0.45, positions[-1] + 0.45)
    return box


def collect_task_questionnaire_means(df, task_col, tasks, prefix):
    cols = find_prefix_columns(df, prefix)
    if not cols:
        return {}

    values_by_task = {}
    for task in tasks:
        task_rows = df[df[task_col].astype(str) == task]
        values = task_rows[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1, skipna=True).dropna()
        values_by_task[task] = values
    return values_by_task


def run_wilcoxon_tests(values_by_task):
    """Paired Wilcoxon signed-rank tests between every pair of tasks.

    The study is within-subjects, so each participant contributes one value per
    task. Values are paired on the shared participant index before testing.
    """
    tests = []
    if not values_by_task or wilcoxon is None:
        return tests

    tasks = list(values_by_task.keys())
    for task_a, task_b in combinations(tasks, 2):
        series_a = pd.Series(values_by_task.get(task_a, pd.Series([], dtype=float)))
        series_b = pd.Series(values_by_task.get(task_b, pd.Series([], dtype=float)))
        if len(series_a) == 0 or len(series_b) == 0:
            continue
        common = series_a.index.intersection(series_b.index)
        paired = pd.concat(
            [
                pd.to_numeric(series_a.loc[common], errors="coerce"),
                pd.to_numeric(series_b.loc[common], errors="coerce"),
            ],
            axis=1,
        ).dropna()
        if paired.empty:
            continue
        tests.append(
            {
                "task_a": task_a,
                "task_b": task_b,
                "values_a": paired.iloc[:, 0],
                "values_b": paired.iloc[:, 1],
            }
        )

    num_tests = len(tests)
    if num_tests == 0:
        return tests

    for i in range(num_tests):
        values_a = tests[i]["values_a"]
        values_b = tests[i]["values_b"]
        try:
            stat = wilcoxon(values_a, values_b, alternative="two-sided", zero_method="wilcox")
            p_value = float(stat.pvalue)
            statistic = float(stat.statistic)
        except Exception:
            p_value = float("nan")
            statistic = float("nan")
        tests[i]["statistic"] = statistic
        tests[i]["p"] = p_value
        tests[i]["p_bonf"] = min(p_value * num_tests, 1.0) if np.isfinite(p_value) else float("nan")
        tests[i]["n_pairs"] = int(len(values_a))
        tests[i]["significant"] = bool(np.isfinite(p_value) and tests[i]["p_bonf"] < 0.05)

    return tests


def p_to_marker(p_value):
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return "ns"


def annotate_significance(ax, task_order, values_by_task, tests):
    if not tests:
        return

    significant = [test for test in tests if test.get("significant")]
    if not significant:
        return

    ymax = None
    ymin = None
    for task in task_order:
        values = values_by_task.get(task, pd.Series([], dtype=float))
        if len(values) == 0:
            continue
        local_max = float(np.max(values))
        local_min = float(np.min(values))
        ymax = local_max if ymax is None else max(ymax, local_max)
        ymin = local_min if ymin is None else min(ymin, local_min)

    if ymax is None or ymin is None:
        return

    y_span = ymax - ymin
    if y_span <= 0:
        y_span = max(abs(ymax), 1.0)

    base = ymax + 0.06 * y_span
    step = 0.10 * y_span
    bar_h = 0.03 * y_span
    x_pos = {task: BOX_X_START + BOX_X_STEP * i for i, task in enumerate(task_order)}

    for level, test in enumerate(significant):
        task_a = test["task_a"]
        task_b = test["task_b"]
        if task_a not in x_pos or task_b not in x_pos:
            continue
        x1 = x_pos[task_a]
        x2 = x_pos[task_b]
        if x1 > x2:
            x1, x2 = x2, x1
        y = base + level * step
        ax.plot([x1, x1, x2, x2], [y, y + bar_h, y + bar_h, y], lw=1.2, c="black")
        ax.text((x1 + x2) / 2.0, y + bar_h, p_to_marker(test["p_bonf"]), ha="center", va="bottom", fontsize=10)

    ax.set_ylim(top=base + len(significant) * step + 0.25 * y_span)


def print_wilcoxon_analysis(values_by_task, title):
    if not values_by_task:
        return

    print("")
    print("=== Wilcoxon signed-rank: %s ===" % title)

    if wilcoxon is None:
        print("scipy is not available. Install with: pip install scipy")
        return

    tests = run_wilcoxon_tests(values_by_task)

    if not tests:
        print("Not enough paired data for pairwise tests.")
        return

    alpha = 0.05
    bonf_alpha = alpha / float(len(tests))
    print("Two-sided paired test, Bonferroni alpha=%.6f (%d comparisons)" % (bonf_alpha, len(tests)))

    for test in tests:
        significant = "yes" if test["significant"] else "no"
        print(
            "%s vs %s | W=%.3f | p=%.6g | p_bonf=%.6g | n_pairs=%d | significant=%s"
            % (
                test["task_a"],
                test["task_b"],
                test["statistic"],
                test["p"],
                test["p_bonf"],
                test["n_pairs"],
                significant,
            )
        )


def print_group_descriptives(values_by_task, title, task_order=None):
    if not values_by_task:
        return

    print("")
    print("=== Descriptive Stats: %s ===" % title)
    order = task_order if task_order else list(values_by_task.keys())
    for task in order:
        values = pd.to_numeric(values_by_task.get(task, pd.Series([], dtype=float)), errors="coerce").dropna()
        n = int(len(values))
        if n == 0:
            print("%s | n=0 | mean ± sd = nan ± nan" % task)
            continue
        mean = float(values.mean())
        sd = float(values.std(ddof=1)) if n > 1 else 0.0
        print("%s | n=%d | mean ± sd = %.1f ± %.1f" % (task, n, mean, sd))


def format_score(value):
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return ""
    return "%.1f" % float(numeric)


def print_individual_participant_scores(df, person_col, task_col, task_order):
    if df.empty:
        return

    score_columns = [
        ("TLX", "TLX_Used"),
        ("TLX Source", "TLX_Source"),
        ("SUS", "SUS_Score"),
    ]
    for col in find_prefix_columns(df, "Additional Q"):
        numeric_values = pd.to_numeric(df[col], errors="coerce")
        if numeric_values.notna().any():
            score_columns.append((ADDITIONAL_QUESTION_TITLES.get(col, col), col))

    print("")
    print("=== Individual Participant Scores ===")
    header = ["Participant", "Task"] + [label for label, _ in score_columns]
    print("\t".join(header))

    people = unique_in_order(normalize_tokens(df[person_col].dropna().tolist()))
    for person in people:
        person_rows = df[df[person_col].astype(str) == person]
        for task in task_order:
            task_rows = person_rows[person_rows[task_col].astype(str) == task]
            if task_rows.empty:
                continue
            row = task_rows.iloc[0]
            output = [person, task]
            for label, col in score_columns:
                if col == "TLX_Source":
                    output.append(str(row.get(col, "")).strip())
                else:
                    output.append(format_score(row.get(col, "")))
            print("\t".join(output))


def normalize_haptic_key(text):
    key = str(text).strip().lower().replace("_", " ")
    key = " ".join(key.split())
    return key


def parse_rank_int(value):
    try:
        rank = int(float(value))
    except Exception:
        return None
    if 1 <= rank <= 3:
        return rank
    return None


def parse_haptic_rank_answer(value):
    result = {}
    if value is None:
        return result
    if isinstance(value, float) and np.isnan(value):
        return result

    # Try dictionary-style answers first (JSON/object-like).
    obj = None
    if isinstance(value, dict):
        obj = value
    else:
        text = str(value).strip()
        if not text:
            return result
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                obj = parsed
        except Exception:
            obj = None
    if isinstance(obj, dict):
        for raw_key, raw_rank in obj.items():
            key = normalize_haptic_key(raw_key)
            label = HAPTIC_INFO_KEY_MAP.get(key)
            if not label:
                continue
            rank = parse_rank_int(raw_rank)
            if rank is not None:
                result[label] = rank
        if result:
            return result

    # Fallback for exported CSV text:
    # "Horizontal distribution of swarm: 1; Relative ...: 2; Disconnection: 3"
    text = str(value).strip()
    if not text:
        return result
    parts = [part.strip() for part in text.split(";") if part.strip()]
    for part in parts:
        if ":" not in part:
            continue
        label_text, rank_text = part.split(":", 1)
        label = HAPTIC_INFO_KEY_MAP.get(normalize_haptic_key(label_text))
        rank = parse_rank_int(rank_text.strip())
        if label and rank is not None:
            result[label] = rank
    return result


def _summarize_haptic_rows(rows):
    values = {label: [] for label in HAPTIC_INFO_ORDER}
    first_count = {label: 0 for label in HAPTIC_INFO_ORDER}

    for rank_map in rows:
        for label in HAPTIC_INFO_ORDER:
            if label in rank_map:
                values[label].append(rank_map[label])
                if rank_map[label] == 1:
                    first_count[label] += 1

    summary = []
    for label in HAPTIC_INFO_ORDER:
        arr = pd.to_numeric(pd.Series(values[label]), errors="coerce").dropna()
        n = int(len(arr))
        if n == 0:
            continue
        mean = float(arr.mean())
        sd = float(arr.std(ddof=1)) if n > 1 else 0.0
        summary.append(
            {
                "label": label,
                "n": n,
                "mean": mean,
                "sd": sd,
                "first_count": int(first_count[label]),
            }
        )
    summary.sort(key=lambda item: item["mean"])
    return summary


def print_haptic_importance_summary(df, task_col="", task_order=None):
    rank_col = ""
    for name in HAPTIC_RANK_COL_CANDIDATES:
        if name in df.columns:
            rank_col = name
            break
    if not rank_col:
        return

    rows = []
    for _, row in df.iterrows():
        rank_map = parse_haptic_rank_answer(row.get(rank_col))
        if rank_map:
            task_name = str(row.get(task_col, "")).strip() if task_col else ""
            rows.append({"task": task_name, "rank_map": rank_map})
    if not rows:
        return

    print("")
    print("=== Haptic Information Importance Ranking ===")
    print("Lower mean rank means higher perceived importance (1 = most important).")

    overall_summary = _summarize_haptic_rows([item["rank_map"] for item in rows])
    if overall_summary:
        print("Overall (n=%d responses):" % len(rows))
        for i, item in enumerate(overall_summary, start=1):
            first_pct = 100.0 * float(item["first_count"]) / float(len(rows))
            print(
                "%d) %s | mean ± sd = %.1f ± %.1f | #1 votes: %d/%d (%.1f%%)"
                % (i, item["label"], item["mean"], item["sd"], item["first_count"], len(rows), first_pct)
            )

    if not task_col:
        return

    ordered_tasks = task_order if task_order else unique_in_order([item["task"] for item in rows])
    for task in ordered_tasks:
        task_rows = [item["rank_map"] for item in rows if item["task"] == task]
        if not task_rows:
            continue
        task_summary = _summarize_haptic_rows(task_rows)
        if not task_summary:
            continue
        print("Task: %s (n=%d responses)" % (task, len(task_rows)))
        for i, item in enumerate(task_summary, start=1):
            first_pct = 100.0 * float(item["first_count"]) / float(len(task_rows))
            print(
                "%d) %s | mean ± sd = %.1f ± %.1f | #1 votes: %d/%d (%.1f%%)"
                % (i, item["label"], item["mean"], item["sd"], item["first_count"], len(task_rows), first_pct)
            )


def _screen_size():
    return 1920, 1080


def tile_figure_windows(figures):
    if not figures:
        return

    screen_w, screen_h = _screen_size()
    for fig in figures:
        manager = getattr(fig.canvas, "manager", None)
        window = getattr(manager, "window", None) if manager is not None else None
        try:
            if window is not None and hasattr(window, "winfo_screenwidth") and hasattr(window, "winfo_screenheight"):
                screen_w = int(window.winfo_screenwidth())
                screen_h = int(window.winfo_screenheight())
                break
            if window is not None and hasattr(window, "screen"):
                screen = window.screen()
                if screen is not None and hasattr(screen, "availableGeometry"):
                    geom = screen.availableGeometry()
                    screen_w = int(geom.width())
                    screen_h = int(geom.height())
                    break
        except Exception:
            continue
    margin_x = 20
    margin_y = 60
    gap_x = 24
    gap_y = 36
    x = margin_x
    y = margin_y
    row_max_h = 0
    fallback_step = 60
    fallback_index = 0
    cascade_point = None

    for fig in figures:
        # Preserve the figure size; only move windows to reduce overlap.
        dpi = fig.get_dpi()
        fig_w = int(fig.get_size_inches()[0] * dpi)
        fig_h = int(fig.get_size_inches()[1] * dpi)

        if x + fig_w > screen_w - margin_x:
            x = margin_x
            y += row_max_h + gap_y
            row_max_h = 0
        if y + fig_h > screen_h - margin_y:
            x = margin_x
            y = margin_y

        manager = getattr(fig.canvas, "manager", None)
        if manager is None:
            x += fig_w + gap_x
            row_max_h = max(row_max_h, fig_h)
            continue
        window = getattr(manager, "window", None)
        moved = False
        try:
            if window is not None and hasattr(window, "cascadeTopLeftFromPoint_"):
                if cascade_point is None:
                    cascade_point = (x, y)
                cascade_point = window.cascadeTopLeftFromPoint_(cascade_point)
                moved = True
            elif window is not None and hasattr(window, "wm_geometry"):
                window.wm_geometry("+%d+%d" % (x, y))
                moved = True
            elif window is not None and hasattr(window, "move"):
                window.move(x, y)
                moved = True
            elif window is not None and hasattr(window, "setGeometry"):
                geometry = window.geometry()
                cur_w = geometry.width() if hasattr(geometry, "width") else fig_w
                cur_h = geometry.height() if hasattr(geometry, "height") else fig_h
                window.setGeometry(x, y, cur_w, cur_h)
                moved = True
            elif window is not None and hasattr(window, "SetPosition"):
                window.SetPosition((x, y))
                moved = True
            elif window is not None and hasattr(window, "setFrameTopLeftPoint_"):
                # macOS Cocoa windows often honor top-left point updates.
                window.setFrameTopLeftPoint_((x, y))
                moved = True
            elif window is not None and hasattr(window, "setFrameOrigin_"):
                window.setFrameOrigin_((x, y))
                moved = True
            elif hasattr(manager, "window") and hasattr(manager.window, "SetPosition"):
                manager.window.SetPosition((x, y))
                moved = True
            elif hasattr(manager, "window") and hasattr(manager.window, "move"):
                manager.window.move(x, y)
                moved = True
        except Exception:
            moved = False

        if not moved:
            # Final fallback: adjust the figure manager geometry string if available.
            try:
                if hasattr(manager, "set_window_geometry"):
                    manager.set_window_geometry(x, y, fig_w, fig_h)
                    moved = True
            except Exception:
                moved = False

        if not moved:
            # Deterministic cascade to avoid exact overlap even when backend ignores moves.
            x = margin_x + fallback_index * fallback_step
            y = margin_y + fallback_index * fallback_step
            fallback_index += 1

        x += fig_w + gap_x
        row_max_h = max(row_max_h, fig_h)


def show_tiled_windows(figures):
    if not figures:
        plt.show()
        return

    # Some backends ignore geometry changes until windows are realized.
    # Show non-blocking first, then re-apply tiling a few times.
    try:
        plt.show(block=False)
        for _ in range(5):
            tile_figure_windows(figures)
            for fig in figures:
                try:
                    fig.canvas.draw_idle()
                except Exception:
                    pass
            plt.pause(0.12)
        plt.show()
    except TypeError:
        tile_figure_windows(figures)
        plt.show()


def select_from_list(prompt, options, min_count=1, max_count=None, select_all_on_empty=False):
    if not options:
        return []

    print(prompt)
    for idx, item in enumerate(options, start=1):
        print("  %d) %s" % (idx, item))

    choice = input("Enter names or numbers (comma-separated): ").strip()
    if not choice:
        if select_all_on_empty:
            return options[:]
        return []

    tokens = [token.strip() for token in choice.split(",") if token.strip()]
    selected = []
    for i in parse_index_tokens(tokens, len(options)):
        selected.append(options[i - 1])
    for token in tokens:
        if not token.isdigit() and "-" not in token:
            selected.append(token)

    selected = unique_in_order(normalize_tokens(selected))
    if min_count and len(selected) < min_count:
        return []
    if max_count is not None and len(selected) > max_count:
        return selected[:max_count]
    return selected


def build_task_participant_groups(df, person_col, task_col, task_order=None):
    groups = {}
    order = task_order if task_order else unique_in_order(normalize_tokens(df[task_col].dropna().tolist()))
    order = order_tasks_preferred(order)
    for task in order:
        task_rows = df[df[task_col].astype(str) == task]
        people = unique_in_order(normalize_tokens(task_rows[person_col].dropna().tolist()))
        if people:
            groups[task] = people
    return groups


def select_participants_gui(grouped_options, all_people):
    if not tk or not grouped_options:
        return None

    state = {"result": None}
    saved_selection = load_participant_selection_cache()
    matched_saved = 0
    root = tk.Tk()
    root.title("Select Participants")
    root.geometry("+80+80")
    root.minsize(920, 440)
    root.update_idletasks()
    root.lift()
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass
    try:
        root.focus_force()
    except Exception:
        pass

    info = tk.Label(
        root,
        text="Select participant(s) per group to include in plotting/statistics.",
        anchor="w",
        justify="left",
    )
    info.grid(row=0, column=0, columnspan=max(1, len(grouped_options)), sticky="ew", padx=10, pady=(10, 6))

    listboxes = {}
    for i, (group_name, options) in enumerate(grouped_options.items()):
        frame = tk.LabelFrame(root, text="%s (%d)" % (group_name, len(options)), padx=6, pady=6)
        frame.grid(row=1, column=i, sticky="nsew", padx=8, pady=8)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        lb = tk.Listbox(frame, selectmode=tk.MULTIPLE, exportselection=False, width=26, height=16)
        lb.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(frame, orient="vertical", command=lb.yview)
        sb.grid(row=0, column=1, sticky="ns")
        lb.config(yscrollcommand=sb.set)

        for item in options:
            lb.insert(tk.END, item)
        if saved_selection:
            for idx, item in enumerate(options):
                if item in saved_selection:
                    lb.select_set(idx)
                    matched_saved += 1
        else:
            lb.select_set(0, tk.END)
        listboxes[group_name] = (lb, options)

    # If cached selection does not match current data, default back to all.
    if saved_selection and matched_saved == 0:
        for lb, options in listboxes.values():
            if options:
                lb.select_set(0, tk.END)

    button_bar = tk.Frame(root)
    button_bar.grid(row=2, column=0, columnspan=max(1, len(grouped_options)), sticky="ew", padx=10, pady=(0, 10))

    def _close_window():
        try:
            root.attributes("-topmost", False)
        except Exception:
            pass
        try:
            root.grab_release()
        except Exception:
            pass
        try:
            root.withdraw()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    def _select_all():
        for lb, options in listboxes.values():
            if options:
                lb.select_set(0, tk.END)

    def _clear_all():
        for lb, options in listboxes.values():
            if options:
                lb.selection_clear(0, tk.END)

    def _apply():
        chosen_set = set()
        for lb, options in listboxes.values():
            for idx in lb.curselection():
                if 0 <= idx < len(options):
                    chosen_set.add(options[idx])
        chosen = [p for p in all_people if p in chosen_set]
        if not chosen:
            if messagebox is not None:
                messagebox.showwarning("No selection", "Select at least one participant.")
            return
        save_participant_selection_cache(chosen)
        state["result"] = chosen
        _close_window()

    def _cancel():
        state["result"] = None
        _close_window()

    tk.Button(button_bar, text="Select all", command=_select_all).pack(side="left", padx=4)
    tk.Button(button_bar, text="Clear all", command=_clear_all).pack(side="left", padx=4)
    tk.Button(button_bar, text="Apply", command=_apply).pack(side="right", padx=4)
    tk.Button(button_bar, text="Cancel", command=_cancel).pack(side="right", padx=4)

    root.rowconfigure(1, weight=1)
    for i in range(len(grouped_options)):
        root.columnconfigure(i, weight=1)

    root.protocol("WM_DELETE_WINDOW", _cancel)
    try:
        root.grab_set()
    except Exception:
        pass
    try:
        root.wait_window()
    except Exception:
        pass
    return state["result"]


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Plot TLX box plots for all available tasks.")
    parser.add_argument("paths", nargs="*", help="Path(s) to CSV file(s)")
    parser.add_argument("--person-col", default="", help="Column name for participant")
    parser.add_argument("--person", action="append", default=[], help="Participant to include (repeatable)")
    parser.add_argument("--tasks", default="", help="Comma-separated list of tasks to include")
    parser.add_argument("--pdf", default="", help="Output PDF base path (files saved as *_01.pdf, *_02.pdf, ...)")
    parser.add_argument("--no-gui", action="store_true", help="Disable file picker")
    return parser.parse_args(argv)


def save_figures_to_pdf_files(figures, csv_paths, pdf_path=""):
    if not figures:
        return []

    if not pdf_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.dirname(script_dir)
        if len(csv_paths) == 1:
            csv_stem = os.path.splitext(os.path.basename(csv_paths[0]))[0]
        else:
            csv_stem = "combined_csv"
        pdf_base = os.path.join(output_dir, csv_stem + "_plots")
    else:
        pdf_base = pdf_path[:-4] if pdf_path.lower().endswith(".pdf") else pdf_path

    digits = max(2, len(str(len(figures))))
    saved_paths = []
    for i, fig in enumerate(figures, start=1):
        out_path = "%s_%0*d.pdf" % (pdf_base, digits, i)
        fig.savefig(out_path, format="pdf", bbox_inches="tight")
        saved_paths.append(out_path)
    return saved_paths


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    paths = list(args.paths or [])
    if not paths:
        if args.no_gui:
            latest_path = latest_csv_in_default_dir()
            if latest_path:
                paths = [latest_path]
                print("Using latest CSV:", latest_path)
        else:
            choice = input("Type 'b' to browse for CSV file(s), or press Enter to use the latest CSV in %s: " % DEFAULT_CSV_DIR).strip().lower()
            if choice == "b":
                paths = pick_csv_files()
            else:
                latest_path = latest_csv_in_default_dir()
                if latest_path:
                    paths = [latest_path]
                    print("Using latest CSV:", latest_path)
    if not paths:
        print("No CSV file selected/found. Pass path(s): python3 scripts/plot_tlx_box.py /path/to/file1.csv /path/to/file2.csv")
        return 1

    if len(paths) > 1:
        print("Combining CSV files:")
        for csv_path in paths:
            print("-", csv_path)

    df = read_csv_files(paths)
    df = compute_sus(compute_tlx(df))

    person_col = args.person_col or guess_column(df, PERSON_COL_CANDIDATES)
    if not person_col:
        print("Could not find a participant column.")
        print("Columns available:")
        for col in df.columns:
            print("-", col)
        return 1

    task_col = guess_column(df, TASK_COL_CANDIDATES)
    if not task_col:
        print("Could not find a task column (Task or Task ID).")
        print("Columns available:")
        for col in df.columns:
            print("-", col)
        return 1
    df = normalize_task_column(df, task_col)

    df, edited = edit_participant_info(df, person_col)
    if edited:
        maybe_save_edited_csv(df, paths[0] if len(paths) == 1 else "")

    people = unique_in_order(normalize_tokens(df[person_col].dropna().tolist()))

    selected_people = normalize_tokens(args.person)
    if not selected_people:
        if tk and not args.no_gui:
            requested_tasks = [normalize_task_name(task) for task in normalize_tokens(args.tasks.split(","))] if args.tasks else []
            task_groups = build_task_participant_groups(df, person_col, task_col, requested_tasks if requested_tasks else None)
            selected_people = select_participants_gui(task_groups, people) or []
            if not selected_people:
                print("Participant selection canceled.")
                return 1
        else:
            selected_people = select_from_list(
                "Select participant(s) to plot:",
                people,
                min_count=1,
                select_all_on_empty=True,
            )

    if not selected_people:
        print("No participants selected.")
        return 1

    df_people = df[df[person_col].astype(str).isin(selected_people)]
    if df_people.empty:
        print("No rows found for selected participant(s).")
        return 1

    tasks = unique_in_order(normalize_tokens(df_people[task_col].dropna().tolist()))
    tasks = order_tasks_preferred(tasks)

    selected_tasks = []
    if args.tasks:
        selected_tasks = [normalize_task_name(task) for task in normalize_tokens(args.tasks.split(","))]
        selected_tasks = order_tasks_preferred(selected_tasks)
    if not selected_tasks:
        selected_tasks = tasks

    df_tasks = df_people[df_people[task_col].astype(str).isin(selected_tasks)]
    if df_tasks.empty:
        print("No rows found for selected tasks.")
        return 1

    data = []
    labels = []
    for task in selected_tasks:
        task_rows = df_tasks[df_tasks[task_col].astype(str) == task]
        values = pd.to_numeric(task_rows["TLX_Used"], errors="coerce").dropna()
        participant_count = int(task_rows[person_col].astype(str).nunique())
        data.append(values)
        labels.append(axis_label(task))

    if not any(len(values) for values in data):
        print("No TLX values available after filtering.")
        return 1

    tlx_values = collect_task_values(df_tasks, task_col, selected_tasks, "TLX_Used", person_col)
    print_individual_participant_scores(df_tasks, person_col, task_col, selected_tasks)
    print_group_descriptives(tlx_values, "TLX", selected_tasks)
    print_wilcoxon_analysis(tlx_values, "TLX")
    additional_by_column = collect_questionnaire_values_by_column(df_tasks, task_col, selected_tasks, "Additional Q", person_col)
    for col_name in additional_by_column:
        print_group_descriptives(additional_by_column[col_name], col_name, selected_tasks)
        print_wilcoxon_analysis(additional_by_column[col_name], col_name)
    interface_choice_panels = collect_interface_choice_panels(df_tasks)
    print_interface_choice_summary(interface_choice_panels)
    print_haptic_importance_summary(df_tasks, task_col, selected_tasks)
    sus_values = collect_task_values(df_tasks, task_col, selected_tasks, "SUS_Score", person_col)
    print_group_descriptives(sus_values, "SUS", selected_tasks)
    print_wilcoxon_analysis(sus_values, "SUS")

    panel_specs = [("NASA TLX", "TLX score", tlx_values)]
    for col_name in additional_by_column:
        panel_specs.append((ADDITIONAL_QUESTION_TITLES.get(col_name, col_name), "Rating", additional_by_column[col_name]))
    if sus_values:
        panel_specs.append(("System Usability Scale", "SUS score", sus_values))

    fig_combined = plot_combined_dashboard(selected_tasks, labels, panel_specs, interface_choice_panels)
    figures = [fig_combined] if fig_combined is not None else []

    saved_pdfs = save_figures_to_pdf_files(figures, paths, args.pdf)
    if saved_pdfs:
        print("Saved plot PDFs:")
        for out_path in saved_pdfs:
            print("-", out_path)

    show_tiled_windows(figures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
