#!/usr/bin/env python3
"""
Plot NASA TLX box plots for all available tasks, filtered by participant(s).

Usage:
  python3 scripts/plot_tlx_box.py /path/to/file.csv
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

try:
    from scipy.stats import mannwhitneyu
except Exception:
    mannwhitneyu = None


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

ADDITIONAL_QUESTION_TITLES = {
    "Additional Q1": "Liking",
    "Additional Q2": "Swarm Awareness",
    "Additional Q3": "Environment Awareness",
}
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
    if "without haptic" in t or ("fpv" in t and "only" in t):
        return 0
    if "minimap" in t or "mini map" in t or ("fpv" in t and "map" in t):
        return 1
    if "with haptic" in t or ("fpv" in t and "haptic" in t):
        return 2
    return 99


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


def pick_csv():
    if not tk or not filedialog:
        return ""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        path = filedialog.askopenfilename(
            parent=root,
            title="Select NASA TLX CSV export",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
    finally:
        root.destroy()
    return path


def latest_csv_in_downloads():
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.isdir(downloads_dir):
        return ""

    latest_path = ""
    latest_mtime = -1.0
    for name in os.listdir(downloads_dir):
        if not name.lower().endswith(".csv"):
            continue
        full_path = os.path.join(downloads_dir, name)
        if not os.path.isfile(full_path):
            continue
        mtime = os.path.getmtime(full_path)
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = full_path
    return latest_path


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

    base, ext = os.path.splitext(original_path)
    default_path = base + "_edited" + (ext or ".csv")
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
            values = values.dropna()
            participant_count = int(task_rows[person_col].astype(str).nunique())
        values_by_task[task] = values
        data.append(values)
        labels.append("%s (%d)" % (task, participant_count))

    if not any(len(values) for values in data):
        return None

    fig, ax = plt.subplots(figsize=(max(5.2, len(labels) * 1.45), 5))
    boxplot_with_labels(ax, data, labels, showmeans=True)
    ax.set_title(title)
    ax.set_ylabel("Rating")
    plt.xticks(rotation=20, ha="right")

    tests = run_mann_whitney_tests(values_by_task)
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
            values = pd.to_numeric(task_rows[col], errors="coerce").dropna()
            participant_count = int(task_rows[person_col].astype(str).nunique()) if not task_rows.empty else 0
            values_by_task[task] = values
            data.append(values)
            labels.append("%s (%d)" % (task, participant_count))

        if not any(len(values) for values in data):
            continue

        question_title = title_map.get(col, "%s: %s" % (title_prefix, col)) if title_map else "%s: %s" % (title_prefix, col)

        fig, ax = plt.subplots(figsize=(max(5.2, len(labels) * 1.45), 5))
        boxplot_with_labels(ax, data, labels, showmeans=True)
        ax.set_title(question_title)
        ax.set_ylabel("Rating")
        plt.xticks(rotation=20, ha="right")
        annotate_significance(ax, tasks, values_by_task, run_mann_whitney_tests(values_by_task))
        fig.tight_layout()
        figures.append(fig)
        values_by_column[col] = values_by_task

    return figures, values_by_column


def collect_questionnaire_values_by_column(df, task_col, tasks, prefix):
    cols = find_prefix_columns(df, prefix)
    values_by_column = {}
    for col in cols:
        values_by_task = {}
        for task in tasks:
            task_rows = df[df[task_col].astype(str) == task]
            values = pd.to_numeric(task_rows[col], errors="coerce").dropna()
            values_by_task[task] = values
        values_by_column[col] = values_by_task
    return values_by_column


def draw_metric_boxplot(ax, task_order, labels, values_by_task, title, ylabel):
    data = [values_by_task.get(task, pd.Series([], dtype=float)) for task in task_order]
    if not any(len(values) for values in data):
        ax.set_visible(False)
        return False

    boxplot_with_labels(ax, data, labels, showmeans=True)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", labelrotation=20)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    annotate_significance(ax, task_order, values_by_task, run_mann_whitney_tests(values_by_task))
    return True


def plot_combined_dashboard(task_order, labels, panel_specs):
    valid_specs = []
    for title, ylabel, values_by_task in panel_specs:
        if values_by_task and any(len(values_by_task.get(task, [])) for task in task_order):
            valid_specs.append((title, ylabel, values_by_task))
    if not valid_specs:
        return None

    n = len(valid_specs)
    rows = 1 if n <= 2 else 2
    cols = int(np.ceil(float(n) / float(rows)))
    fig, axes = plt.subplots(rows, cols, figsize=(max(8.6, cols * 5.8), max(4.6 * rows, 5.2)))
    axes = np.atleast_1d(axes).flatten()

    for i, spec in enumerate(valid_specs):
        title, ylabel, values_by_task = spec
        draw_metric_boxplot(axes[i], task_order, labels, values_by_task, title, ylabel)

    for j in range(len(valid_specs), len(axes)):
        axes[j].set_visible(False)

    fig.suptitle("NASA TLX and Questionnaire Summary", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return fig


def collect_task_values(df, task_col, tasks, value_col):
    values_by_task = {}
    for task in tasks:
        task_rows = df[df[task_col].astype(str) == task]
        values = pd.to_numeric(task_rows[value_col], errors="coerce").dropna()
        values_by_task[task] = values
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


def run_mann_whitney_tests(values_by_task):
    tests = []
    if not values_by_task or mannwhitneyu is None:
        return tests

    tasks = list(values_by_task.keys())
    for task_a, task_b in combinations(tasks, 2):
        values_a = values_by_task.get(task_a, pd.Series([], dtype=float))
        values_b = values_by_task.get(task_b, pd.Series([], dtype=float))
        if len(values_a) == 0 or len(values_b) == 0:
            continue
        tests.append(
            {
                "task_a": task_a,
                "task_b": task_b,
                "values_a": values_a,
                "values_b": values_b,
            }
        )

    num_tests = len(tests)
    if num_tests == 0:
        return tests

    for i in range(num_tests):
        stat = mannwhitneyu(tests[i]["values_a"], tests[i]["values_b"], alternative="two-sided")
        p_value = float(stat.pvalue)
        tests[i]["U"] = float(stat.statistic)
        tests[i]["p"] = p_value
        tests[i]["p_bonf"] = min(p_value * num_tests, 1.0)
        tests[i]["significant"] = tests[i]["p_bonf"] < 0.05

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


def print_mann_whitney_analysis(values_by_task, title):
    if not values_by_task:
        return

    print("")
    print("=== Mann-Whitney U: %s ===" % title)

    if mannwhitneyu is None:
        print("scipy is not available. Install with: pip install scipy")
        return

    tests = run_mann_whitney_tests(values_by_task)

    if not tests:
        print("Not enough data for pairwise tests.")
        return

    alpha = 0.05
    bonf_alpha = alpha / float(len(tests))
    print("Two-sided test, Bonferroni alpha=%.6f (%d comparisons)" % (bonf_alpha, len(tests)))

    for test in tests:
        significant = "yes" if test["significant"] else "no"
        print(
            "%s vs %s | U=%.3f | p=%.6g | p_bonf=%.6g | n1=%d n2=%d | significant=%s"
            % (
                test["task_a"],
                test["task_b"],
                test["U"],
                test["p"],
                test["p_bonf"],
                len(test["values_a"]),
                len(test["values_b"]),
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
    parser.add_argument("path", nargs="?", help="Path to CSV file")
    parser.add_argument("--person-col", default="", help="Column name for participant")
    parser.add_argument("--person", action="append", default=[], help="Participant to include (repeatable)")
    parser.add_argument("--tasks", default="", help="Comma-separated list of tasks to include")
    parser.add_argument("--pdf", default="", help="Output PDF base path (files saved as *_01.pdf, *_02.pdf, ...)")
    parser.add_argument("--no-gui", action="store_true", help="Disable file picker")
    return parser.parse_args(argv)


def save_figures_to_pdf_files(figures, csv_path, pdf_path=""):
    if not figures:
        return []

    if not pdf_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.dirname(script_dir)
        csv_stem = os.path.splitext(os.path.basename(csv_path))[0] if csv_path else "plots"
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

    path = args.path or ""
    if not path:
        if args.no_gui:
            path = latest_csv_in_downloads()
            if path:
                print("Using latest CSV:", path)
        else:
            choice = input("Type 'b' to browse for a CSV file, or press Enter to use the latest CSV in Downloads: ").strip().lower()
            if choice == "b":
                path = pick_csv()
            else:
                path = latest_csv_in_downloads()
                if path:
                    print("Using latest CSV:", path)
    if not path:
        print("No CSV file selected/found. Pass a path: python3 scripts/plot_tlx_box.py /path/to/file.csv")
        return 1

    df = pd.read_csv(path)
    df = compute_tlx(df)

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

    df, edited = edit_participant_info(df, person_col)
    if edited:
        maybe_save_edited_csv(df, path)

    people = unique_in_order(normalize_tokens(df[person_col].dropna().tolist()))

    selected_people = normalize_tokens(args.person)
    if not selected_people:
        if tk and not args.no_gui:
            requested_tasks = normalize_tokens(args.tasks.split(",")) if args.tasks else []
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
        selected_tasks = normalize_tokens(args.tasks.split(","))
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
        labels.append("%s (%d)" % (task, participant_count))

    if not any(len(values) for values in data):
        print("No TLX values available after filtering.")
        return 1

    tlx_values = collect_task_values(df_tasks, task_col, selected_tasks, "TLX_Used")
    print_group_descriptives(tlx_values, "TLX", selected_tasks)
    print_mann_whitney_analysis(tlx_values, "TLX")
    additional_by_column = collect_questionnaire_values_by_column(df_tasks, task_col, selected_tasks, "Additional Q")
    for col_name in additional_by_column:
        print_group_descriptives(additional_by_column[col_name], col_name, selected_tasks)
        print_mann_whitney_analysis(additional_by_column[col_name], col_name)
    print_haptic_importance_summary(df_tasks, task_col, selected_tasks)
    embodiment_values = collect_task_questionnaire_means(df_tasks, task_col, selected_tasks, "SUS Q")
    print_group_descriptives(embodiment_values, "System Usability Scale (row mean)", selected_tasks)
    print_mann_whitney_analysis(embodiment_values, "System Usability Scale (row mean)")

    panel_specs = [("NASA TLX", "TLX score", tlx_values)]
    for col_name in additional_by_column:
        panel_specs.append((ADDITIONAL_QUESTION_TITLES.get(col_name, col_name), "Rating", additional_by_column[col_name]))
    if embodiment_values:
        panel_specs.append(("System Usability Scale (mean)", "Rating", embodiment_values))

    fig_combined = plot_combined_dashboard(selected_tasks, labels, panel_specs)
    figures = [fig_combined] if fig_combined is not None else []

    saved_pdfs = save_figures_to_pdf_files(figures, path, args.pdf)
    if saved_pdfs:
        print("Saved plot PDFs:")
        for out_path in saved_pdfs:
            print("-", out_path)

    show_tiled_windows(figures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
