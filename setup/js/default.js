$(document).ready(function() {

	/* functions */

	/* randomly shuffle an array */

	function shuffle(array) {
		var top = array.length,
			tmp, current;

		if(top) {
			while(--top) {
				current = Math.floor(Math.random() * (top + 1));
				tmp = array[current];
				array[current] = array[top];
				array[top] = tmp;
			}
		}

		return array;
	}

	/* create an array of pairs. formula: n! / ( (n - k)! * k! ) */

	function pair_combinator(array) {

		var length = array.length,
			result = [],
			counter = 0,
			i, j;

		for (i = 0; i < length; i++) {
			for (j = i; j < length - 1; j++) {
				result[counter] = shuffle([ [ array[i][0], array[i][1] ], [ array[j + 1][0], array[j + 1][1] ] ]);
				counter++;
			}
		}

		return shuffle(result);

	}

	/* creates an array with a given length and fills it up with a given value */

	function new_filled_array(length, value) {
		var array = new Array(length);
		while (--length >= 0) {
			array[length] = value;
		}
		return array;
	}

	function csv_escape(value) {
		var string = (value === null || value === undefined) ? "" : String(value);
		if (string.search(/("|,|\n|\r)/g) >= 0) {
			string = '"' + string.replace(/"/g, '""') + '"';
		}
		return string;
	}

	function escape_html(value) {
		var string = (value === null || value === undefined) ? "" : String(value);
		return string
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	}

	function is_additional_text_question(index) {
		return additional_question_types && additional_question_types[index] === "text";
	}

	function is_additional_choice_question(index) {
		return additional_question_types && additional_question_types[index] === "choice";
	}

	function is_additional_rank_question(index) {
		return additional_question_types && additional_question_types[index] === "rank";
	}

	function build_rank_default() {
		return "";
	}

	function is_rank_default_answer(value) {
		var obj = parse_rank_answer(value);
		if (!obj) {
			return false;
		}
		for (var i = 0; i < additional_rank_items.length; i++) {
			var key = additional_rank_items[i].key;
			if (obj[key] !== i + 1) {
				return false;
			}
		}
		return true;
	}

	function parse_rank_answer(value) {
		if (value === null || value === undefined || value === "") {
			return null;
		}
		if (typeof value === "object") {
			return value;
		}
		var parsed = safe_parse_json(value);
		if (parsed && typeof parsed === "object") {
			return parsed;
		}
		return null;
	}

	function format_rank_answer(value) {
		var obj = parse_rank_answer(value);
		if (!obj) {
			return (value === null || value === undefined) ? "" : String(value);
		}
		var parts = [];
		for (var i = 0; i < additional_rank_items.length; i++) {
			var key = additional_rank_items[i].key;
			if (obj[key] !== undefined && obj[key] !== null && obj[key] !== "") {
				parts.push(additional_rank_items[i].label + ": " + obj[key]);
			}
		}
		return parts.length ? parts.join("; ") : "";
	}

	function collect_rank_answer(container) {
		var obj = {};
		container.find("select").each(function() {
			var key = $(this).attr("data-key"),
				value = $(this).val();
			if (key && value) {
				obj[key] = parseInt(value, 10);
			}
		});
		if ($.isEmptyObject(obj)) {
			return "";
		}
		return JSON.stringify(obj);
	}

	function set_rank_selects(container, answer) {
		var obj = parse_rank_answer(answer) || {};
		container.find("select").each(function() {
			var key = $(this).attr("data-key");
			if (obj[key] !== undefined && obj[key] !== null) {
				$(this).val(String(obj[key]));
			} else {
				$(this).val("");
			}
		});
	}

	function build_additional_defaults() {
		var defaults = [];
		for (var i = 0; i < additional_questions.length; i++) {
			if (is_additional_text_question(i) || is_additional_choice_question(i)) {
				defaults[i] = "";
			} else if (is_additional_rank_question(i)) {
				defaults[i] = build_rank_default();
			} else {
				defaults[i] = 3;
			}
		}
		return defaults;
	}

	function pad2(number) {
		return (number < 10 ? "0" : "") + number;
	}

	function get_label_text(id) {
		var label = $("label[for='" + id + "']");
		return label.length ? label.html() : id;
	}

	function build_participant_label(name, camipro) {
		return name + " (" + camipro + ")";
	}

	function build_participant_id(name, camipro) {
		return (name + "_" + camipro).toLowerCase().split(" ").join("_");
	}

	function parse_participant_label(label) {
		var text = (label === null || label === undefined) ? "" : String(label),
			match = text.match(/^(.*)\s\(([^()]*)\)$/);
		if (!match) {
			return {
				name: text,
				camipro: ""
			};
		}
		return {
			name: $.trim(match[1]),
			camipro: $.trim(match[2])
		};
	}

	function format_proband_label(label) {
		var safe = (label === null || label === undefined) ? "" : String(label);
		return "<span class='proband-name'>" + safe + "</span>";
	}

	function status_label(is_done) {
		return is_done ? "Yes" : "No";
	}

	function get_task_list() {
		var tasks = [];
		$(".step_1 .second .list label").each(function() {
			tasks.push({
				id: $(this).attr("for"),
				label: $(this).html()
			});
		});
		return tasks;
	}

	function safe_parse_json(raw) {
		try {
			return JSON.parse(raw);
		} catch (error) {
			return null;
		}
	}

	function get_demand_index(id) {
		for (var i = 0; i < demands.length; i++) {
			if (demands[i][0] === id) {
				return i;
			}
		}
		return -1;
	}

	function pair_key(id1, id2) {
		var index1 = get_demand_index(id1),
			index2 = get_demand_index(id2);

		if (index1 === -1 || index2 === -1) {
			return id1 + "|" + id2;
		}

		if (index1 > index2) {
			return id2 + "|" + id1;
		}
		return id1 + "|" + id2;
	}

	function build_pairs_list() {
		var list = [];
		for (var i = 0; i < demands.length; i++) {
			for (var j = i + 1; j < demands.length; j++) {
				list.push({
					a: demands[i],
					b: demands[j],
					key: pair_key(demands[i][0], demands[j][0])
				});
			}
		}
		return list;
	}

	function sanitize_tasks_list(tasks) {
		var cleaned = [],
			removed = {
				flight_simulation: true,
				drinking_beer: true
			};

		if (tasks && tasks.length) {
			for (var i = 0; i < tasks.length; i++) {
				var item = tasks[i];
				if (!item || !item.id) {
					continue;
				}
				if (removed[item.id]) {
					continue;
				}
				cleaned.push(item);
			}
		}

		return cleaned;
	}

	function prune_removed_tasks() {
		var removed = {
			flight_simulation: true,
			drinking_beer: true
		};

		for (var i = 0; i < final_result.length; i++) {
			var tasks = final_result[i].tasks || [];
			for (var j = tasks.length - 1; j >= 0; j--) {
				if (removed[tasks[j].name]) {
					tasks.splice(j, 1);
				}
			}
		}

		for (var key in in_progress) {
			if (in_progress.hasOwnProperty(key)) {
				var parts = key.split("|");
				if (parts.length >= 2 && removed[parts[1]]) {
					delete in_progress[key];
				}
			}
		}
	}

	function compute_weights_from_pairs(pair_choices) {
		var weights = new_filled_array(demands.length, 0);
		if (!pair_choices) {
			return weights;
		}

		for (var key in pair_choices) {
			if (pair_choices.hasOwnProperty(key)) {
				var choice = pair_choices[key],
					index = get_demand_index(choice);
				if (index >= 0) {
					weights[index] += 1;
				}
			}
		}
		return weights;
	}

	function derive_pair_choices_from_weights(weights) {
		var pairs = build_pairs_list(),
			choices = {},
			remaining = weights ? weights.slice(0) : new_filled_array(demands.length, 0);

		for (var i = 0; i < pairs.length; i++) {
			var a_id = pairs[i].a[0],
				b_id = pairs[i].b[0],
				a_index = get_demand_index(a_id),
				b_index = get_demand_index(b_id),
				choice = a_id;

			if (remaining[b_index] > remaining[a_index]) {
				choice = b_id;
			}

			choices[pairs[i].key] = choice;

			var choice_index = get_demand_index(choice);
			if (choice_index >= 0 && remaining[choice_index] > 0) {
				remaining[choice_index] -= 1;
			}
		}

		return choices;
	}

	/* variables */

	var settings,
		random_pairs,
		data_object,
		counter,
		pairs_length,
		final_result = [],
		demands = [
			["md", "Mental demand"],
			["pd", "Physical demand"],
			["td", "Temporal demand"],
			["op", "Performance"],
			["ef", "Effort"],
			["fr", "Frustration"]
		],
		additional_questions = [
			"Which interface do you prefer?",
			"Do you play video games (yes/no), how many hours per week?",
			"Do you have previous experience with teleoperation (e.g. drone flying)?",
			"Do you have any general feedback on the experiment?"
		],
		additional_question_types = [
			"choice",
			"text",
			"text",
			"text"
		],
		additional_choice_options = [
			"Joystick",
			"Body-motion control",
			"Same"
		],
		additional_rank_items = [],
		embodiment_questions = [
			"I think that I would like to use this interface frequently.",
			"I found the interface unnecessarily complex.",
			"I thought the interface was easy to use.",
			"I think that I would need the support of a technical person to be able to use this interface.",
			"I found the various functions in this interface were well integrated.",
			"I thought there was too much inconsistency in this interface.",
			"I would imagine that most people would learn to use this interface very quickly.",
			"I found the interface very cumbersome to use.",
			"I felt very confident using the interface.",
			"I needed to learn a lot of things before I could get going with this interface."
		],
		demand_descriptions = [
			"How mentally demanding was the task?",
			"How physically demanding was the task?",
			"How hurried or rushed was the pace of the task?",
			"How successful were you in accomplishing what you were asked to do?",
			"How hard did you have to work to accomplish your level of performance?",
			"How insecure, discouraged, irritated, stressed, and annoyed were you?"
		],
		tableoutput = "",
		no_score = "–",
		storage_key = "nasa_tlx_autosave_v1",
		editing_target = null,
		in_progress = {},
		editing_pair_choices = null,
		editing_rating_scale = 100,
		current_questionnaire = "tlx",
		default_page_title = "",
		additional_data = null,
		embodiment_data = null,
		suppress_history = false;

	function has_exportable_data() {
		for (var i = 0; i < final_result.length; i++) {
			for (var j = 0; j < final_result[i].tasks.length; j++) {
				var task = final_result[i].tasks[j];
				if (task.tlx !== undefined && task.tlx !== null) {
					return true;
				}
				if (task.additional && task.additional.answers && task.additional.answers.length) {
					return true;
				}
				if (has_completed_embodiment_data(task)) {
					return true;
				}
			}
		}
		return false;
	}

	function set_page_title(mode) {
		if (!default_page_title) {
			default_page_title = $("header h1").html();
		}
		if (mode === "additional" || mode === "embodiment" || mode === "overview" || mode === "step1") {
			$("header h1").html("Symbiotic aerial swarm");
		} else {
			$("header h1").html(default_page_title);
		}
	}

	function set_current_questionnaire(mode, skip_title) {
		if (mode === "additional" || mode === "embodiment") {
			current_questionnaire = mode;
		} else {
			current_questionnaire = "tlx";
		}
		if (!skip_title) {
			if ($(".step_0").is(":visible") || $(".step_1").is(":visible")) {
				set_page_title("overview");
			} else {
				set_page_title(current_questionnaire);
			}
		}
	}

	function push_history_state(state, replace) {
		if (suppress_history || !window.history || !window.history.pushState) {
			return;
		}
		if (replace) {
			window.history.replaceState(state, "", "");
		} else {
			window.history.pushState(state, "", "");
		}
	}

	function select_radio(name, id) {
		if (!id) {
			return;
		}
		var input = $("input[name='" + name + "'][id='" + id + "']");
		if (input.length) {
			input.prop("checked", true);
		}
	}

	function navigate_to_state(state) {
		if (!state || !state.view) {
			return;
		}

		suppress_history = true;
		set_current_questionnaire(state.questionnaire || current_questionnaire, true);

		$(".info").remove();
	$(".step_0, .step_1, .step_2, .step_3, .step_4, .step_additional, .step_embodiment").hide();

		if (state.proband) {
			select_radio("probands", state.proband);
		}
		if (state.task) {
			select_radio("tasks", state.task);
		}

		if (state.view === "overview") {
			if (has_exportable_data()) {
				render_overview();
			} else {
				show_empty_overview();
			}
			$(".step_0").show();
			set_page_title("overview");
			suppress_history = false;
			return;
		}

		if (state.view === "step1") {
			$(".step_1").show();
			set_page_title("step1");
			suppress_history = false;
			return;
		}

		if (!state.proband || !state.task) {
			$(".step_0").show();
			suppress_history = false;
			return;
		}

		settings = [
			state.proband,
			get_label_text(state.proband),
			state.task,
			get_label_text(state.task)
		];

		if (state.view === "step2") {
			enter_step2(settings[1], settings[3], get_progress_entry(state.proband, state.task, "tlx"));
			suppress_history = false;
			return;
		}

		if (state.view === "step3") {
			var progress = state.progress || get_progress_entry(state.proband, state.task, "tlx"),
				ref = get_task_reference(state.proband, state.task);

			if (!progress && ref && ref.task.data) {
				var pair_order = ref.task.data.pair_order || build_pairs_list(),
					choice_count = ref.task.data.pair_choices ? Object.keys(ref.task.data.pair_choices).length : 0,
					total_pairs = pair_order.length;
				progress = {
					data_object: ref.task.data,
					random_pairs: pair_order,
					counter: Math.min(choice_count, total_pairs - 1),
					pairs_length: Math.max(total_pairs - choice_count, 0),
					started: choice_count > 0
				};
			}

			if (progress) {
				enter_step3(settings[1], settings[3], progress);
			} else {
				enter_step2(settings[1], settings[3], get_progress_entry(state.proband, state.task, "tlx"));
			}
			suppress_history = false;
			return;
		}

		if (state.view === "additional") {
			enter_additional(settings[1], settings[3], get_progress_entry(state.proband, state.task, "additional"));
			suppress_history = false;
			return;
		}

		if (state.view === "embodiment") {
			enter_embodiment(settings[1], settings[3], get_progress_entry(state.proband, state.task, "embodiment"));
			suppress_history = false;
			return;
		}

		if (state.view === "results") {
			if (state.questionnaire === "additional") {
				show_additional_results(state.proband, state.task, false);
			} else if (state.questionnaire === "embodiment") {
				show_embodiment_results(state.proband, state.task, false);
			} else {
				show_task_results(state.proband, state.task, false);
			}
			$(".step_4").show();
			set_page_title(state.questionnaire || current_questionnaire);
			suppress_history = false;
			return;
		}

		suppress_history = false;
	}

	function update_export_state() {
		var has_data = has_exportable_data();
		$("#export_csv").prop("disabled", !has_data);
		$("#review_data").prop("disabled", !has_data);
	}

	function progress_key(proband_id, task_id, questionnaire) {
		var type = questionnaire || "tlx";
		return proband_id + "|" + task_id + "|" + type;
	}

	function get_progress_entry(proband_id, task_id, questionnaire) {
		return in_progress[progress_key(proband_id, task_id, questionnaire)];
	}

	function set_progress_entry(proband_id, task_id, entry, questionnaire) {
		in_progress[progress_key(proband_id, task_id, questionnaire)] = entry;
	}

	function clear_progress_entry(proband_id, task_id, questionnaire) {
		delete in_progress[progress_key(proband_id, task_id, questionnaire)];
	}

	function ensure_data_object(data) {
		var obj = data || {};
		if (!obj.button_clicks || obj.button_clicks.length !== demands.length) {
			obj.button_clicks = new_filled_array(demands.length, 0);
		}
		if (!obj.slider_value || obj.slider_value.length !== demands.length) {
			obj.slider_value = new_filled_array(demands.length, 50);
		}
		if (!obj.pair_choices) {
			obj.pair_choices = {};
		}
		if (!obj.rating_scale) {
			var max_value = 0;
			for (var i = 0; i < obj.slider_value.length; i++) {
				if (obj.slider_value[i] > max_value) {
					max_value = obj.slider_value[i];
				}
			}
			obj.rating_scale = (max_value > 20) ? 100 : 20;
		}
		return obj;
	}

	function normalize_progress(entry) {
		if (!entry) {
			return null;
		}
		entry.data_object = ensure_data_object(entry.data_object);
		entry.counter = entry.counter || 0;
		entry.started = !!entry.started;
		if (entry.random_pairs && entry.random_pairs.length) {
			if (entry.pairs_length === undefined || entry.pairs_length === null) {
				entry.pairs_length = Math.max(entry.random_pairs.length - entry.counter, 0);
			} else {
				entry.pairs_length = Math.min(entry.pairs_length, entry.random_pairs.length - entry.counter);
			}
		} else {
			entry.pairs_length = 0;
		}
		return entry;
	}

	function ensure_additional_data(data) {
		var obj = data || {};
		var defaults = build_additional_defaults();
		if (!obj.answers || !obj.answers.length) {
			obj.answers = defaults.slice();
			return obj;
		}
		if (obj.answers.length === 7 && additional_questions.length === 4) {
			obj.answers = [
				defaults[0],
				obj.answers[4] || defaults[1],
				obj.answers[5] || defaults[2],
				obj.answers[6] || defaults[3]
			];
			return obj;
		}
		if (obj.answers.length !== additional_questions.length) {
			var merged = defaults.slice();
			for (var i = 0; i < Math.min(obj.answers.length, merged.length); i++) {
				merged[i] = obj.answers[i];
			}
			obj.answers = merged;
		} else {
			for (var j = 0; j < obj.answers.length; j++) {
				if (obj.answers[j] === undefined || obj.answers[j] === null) {
					obj.answers[j] = defaults[j];
				}
			}
		}
		if (!obj.rank_migrated) {
			for (var k = 0; k < obj.answers.length; k++) {
				if (is_additional_rank_question(k) && is_rank_default_answer(obj.answers[k])) {
					obj.answers[k] = build_rank_default();
				}
			}
			obj.rank_migrated = true;
		}
		return obj;
	}

	function ensure_embodiment_data(data) {
		var obj = data || {};
		if (!obj.answers || obj.answers.length !== embodiment_questions.length) {
			obj.answers = new_filled_array(embodiment_questions.length, 3);
		}
		return obj;
	}

	function has_completed_embodiment_data(task) {
		return task && task.embodiment && task.embodiment.answers && task.embodiment.answers.length === embodiment_questions.length;
	}

	function refresh_review_options() {
		var proband_select = $("#review_proband"),
			task_select = $("#review_task");

		if (!proband_select.length || !task_select.length) {
			return;
		}

		proband_select.empty();
		$(".step_1 .first .list label").each(function() {
			proband_select.append(
				"<option value='" + $(this).attr("for") + "'>" + $(this).html() + "</option>"
			);
		});

		task_select.empty();
		$(".step_1 .second .list label").each(function() {
			task_select.append(
				"<option value='" + $(this).attr("for") + "'>" + $(this).html() + "</option>"
			);
		});
	}

	function delete_task_data(task_id) {
		$(".step_1 .second .list input[id='" + task_id + "']").closest("div").remove();
		var first_task = $(".step_1 .second .list input[type='radio']").first();
		if (first_task.length) {
			first_task.prop("checked", true);
		}

		save_state();
		refresh_review_options();
		update_export_state();

		if (has_exportable_data()) {
			render_overview();
		} else {
			show_empty_overview();
		}
	}

	function get_task_reference(proband_id, task_id) {
		for (var i = 0; i < final_result.length; i++) {
			if (final_result[i].proband === proband_id) {
				for (var j = 0; j < final_result[i].tasks.length; j++) {
					if (final_result[i].tasks[j].name === task_id) {
						return {
							proband_index: i,
							task_index: j,
							proband: final_result[i],
							task: final_result[i].tasks[j]
						};
					}
				}
			}
		}
		return null;
	}

	function build_task_output(ratings, weights) {
		var sum = 0,
			weight_sum = 0,
			output = "<table><thead><tr><th>Demand</th><th>Rating</th><th>Weight</th><th>Product</th></tr></thead><tbody>";

		for (var j = 0; j < demands.length; j++ ) {
			var rating = (ratings[j] !== undefined) ? ratings[j] : "",
				weight = (weights[j] !== undefined) ? weights[j] : "",
				product = "";

			if (rating !== "" && weight !== "") {
				product = rating * weight;
				sum += product;
				weight_sum += weight;
			}

			output += "<tr><td>" + demands[j][1] + "</td><td>" + rating + "</td><td>" + weight + "</td><td>" + product + "</td></tr>";
		}

		output += "<tr><th colspan='3'>Product sum</th><td>" + sum + "</td></tr>";
		output += "<tr><th colspan='3'>Total weights</th><td>" + weight_sum + "</td></tr>";
		output += "<tr><th colspan='3'>Rounded TLX score</th><td><strong>" + (weight_sum ? Math.round(sum/weight_sum) : no_score) + "</strong></td></tr></tbody></table>";

		return {
			output: output,
			sum: sum,
			weight_sum: weight_sum,
			tlx: weight_sum ? Math.round(sum/weight_sum) : null
		};
	}

	function render_edit_panel(proband_id, task_id, task) {
		var ratings = (task.data && task.data.slider_value) ? task.data.slider_value : [],
			weights = (task.data && task.data.button_clicks) ? task.data.button_clicks : [],
			rating_scale = (task.data && task.data.rating_scale) ? task.data.rating_scale : 100,
			pair_choices = (task.data && task.data.pair_choices && !$.isEmptyObject(task.data.pair_choices)) ? task.data.pair_choices : derive_pair_choices_from_weights(weights),
			pairs = build_pairs_list(),
			html = "<h3>Edit data for " + format_proband_label(get_label_text(proband_id)) + " / " + get_label_text(task_id) + "</h3>";

		editing_pair_choices = $.extend(true, {}, pair_choices);
		editing_rating_scale = rating_scale;
		for (var p = 0; p < pairs.length; p++) {
			if (!editing_pair_choices[pairs[p].key]) {
				editing_pair_choices[pairs[p].key] = pairs[p].a[0];
			}
		}

		html += "<div class='edit_sliders'>";

		for (var i = 0; i < demands.length; i++) {
			var rating_value = (ratings[i] !== undefined) ? ratings[i] : 10,
				slider_value = rating_value;

			if (rating_scale > 20) {
				slider_value = Math.round(slider_value / (rating_scale / 20));
			}
			if (slider_value < 1) {
				slider_value = 1;
			}

			html += "<section>";
			html += "<h4>" + demands[i][1] + "</h4>";
			html += "<p>" + demand_descriptions[i] + "</p>";
			html += "<div class='slider edit_slider" + (demands[i][0] === "op" ? " performance" : "") + "' data-index='" + i + "' data-value='" + slider_value + "'></div>";
			html += "<p class='edit_rating_value'>Rating: <strong data-index='" + i + "'>" + slider_value + "</strong></p>";
			html += "</section>";
		}

		html += "</div>";
		html += "<div class='edit_pairs'><h4>Pair-wise comparison</h4>";
		for (var k = 0; k < pairs.length; k++) {
			var pair = pairs[k],
				choice = editing_pair_choices[pair.key] || pair.a[0],
				a_selected = (choice === pair.a[0]) ? " selected" : "",
				b_selected = (choice === pair.b[0]) ? " selected" : "";

			html += "<div class='pair_row'>";
			html += "<button class='edit_pair_option" + a_selected + "' type='button' data-pair='" + pair.key + "' data-choice='" + pair.a[0] + "'>" + pair.a[1] + "</button> or ";
			html += "<button class='edit_pair_option" + b_selected + "' type='button' data-pair='" + pair.key + "' data-choice='" + pair.b[0] + "'>" + pair.b[1] + "</button>";
			html += "</div>";
		}
		html += "</div>";

		var derived_weights = compute_weights_from_pairs(editing_pair_choices);
		html += "<table class='edit_weights'><thead><tr><th>Demand</th><th>Weight</th></tr></thead><tbody>";
		for (var j = 0; j < demands.length; j++) {
			html += "<tr><td>" + demands[j][1] + "</td>";
			html += "<td class='edit_weight_value' data-index='" + j + "'>" + derived_weights[j] + "</td></tr>";
		}
		html += "</tbody></table>";
		html += "<p class='edit_error'></p>";
		html += "<button id='save_edit' type='button'>Save changes</button>";
		html += "<button id='cancel_edit' type='button'>Cancel</button>";

		$(".edit_panel").html(html);

		$(".edit_panel .edit_slider").each(function() {
			var slider = $(this),
				index = slider.data("index"),
				start_value = parseInt(slider.attr("data-value"), 10);

			slider.slider({
				max: 20,
				min: 1,
				step: 1,
				value: start_value,
				slide: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				},
				change: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				}
			});
		});

		update_edit_weights_display();
	}

	function open_edit_panel(proband_id, task_id) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref) {
			return false;
		}
		render_edit_panel(proband_id, task_id, ref.task);
		$(".edit_panel").show();
		return true;
	}

	function render_additional_edit_panel(proband_id, task_id, task) {
		var answers = (task.additional && task.additional.answers) ? task.additional.answers : [],
			html = "<h3>Edit additional questions for " + format_proband_label(get_label_text(proband_id)) + " / " + get_label_text(task_id) + "</h3>";

		html += "<div class='edit_sliders'>";
		for (var i = 0; i < additional_questions.length; i++) {
			html += "<section>";
			html += "<h4>" + escape_html(additional_questions[i]) + "</h4>";
			if (is_additional_text_question(i)) {
				html += "<textarea class='edit_additional_text' data-index='" + i + "' rows='3'></textarea>";
			} else if (is_additional_choice_question(i)) {
				html += "<div class='additional_choice edit_additional_choice' data-index='" + i + "'>";
				for (var c = 0; c < additional_choice_options.length; c++) {
					html += "<label><input type='radio' name='edit_additional_choice_" + i + "' value='" + escape_html(additional_choice_options[c]) + "'> " + escape_html(additional_choice_options[c]) + "</label>";
				}
				html += "</div>";
			} else if (is_additional_rank_question(i)) {
				html += "<div class='additional_rank edit_additional_rank' data-index='" + i + "'>";
				for (var r = 0; r < additional_rank_items.length; r++) {
					html += "<div class='additional_rank_item'>";
					html += "<label>" + escape_html(additional_rank_items[r].label) + "</label>";
					html += "<select data-key='" + additional_rank_items[r].key + "'>";
					html += "<option value=''>Select rank</option>";
					html += "<option value='1'>1</option>";
					html += "<option value='2'>2</option>";
					html += "<option value='3'>3</option>";
					html += "</select>";
					html += "</div>";
				}
				html += "</div>";
			} else {
				var answer_value = parseInt(answers[i], 10);
				if (isNaN(answer_value)) {
					answer_value = 3;
				}
				if (answer_value < 1) {
					answer_value = 1;
				}
				if (answer_value > 5) {
					answer_value = 5;
				}
				html += "<div class='slider edit_additional_slider' data-index='" + i + "' data-value='" + answer_value + "'></div>";
				html += "<p class='edit_rating_value'>Answer: <strong data-index='" + i + "'>" + answer_value + "</strong></p>";
			}
			html += "</section>";
		}
		html += "</div>";
		html += "<p class='edit_error'></p>";
		html += "<button id='save_edit' type='button'>Save changes</button>";
		html += "<button id='cancel_edit' type='button'>Cancel</button>";

		$(".edit_panel").html(html);

		$(".edit_panel .edit_additional_text").each(function() {
			var index = parseInt($(this).attr("data-index"), 10),
				value = (answers[index] !== undefined && answers[index] !== null) ? answers[index] : "";
			$(this).val(value);
		});

		$(".edit_panel .edit_additional_choice").each(function() {
			var index = parseInt($(this).attr("data-index"), 10),
				value = (answers[index] !== undefined && answers[index] !== null) ? answers[index] : "";
			$(this).find("input[type='radio']").prop("checked", false);
			if (value) {
				$(this).find("input[type='radio']").filter(function() {
					return $(this).val() === value;
				}).prop("checked", true);
			}
		});

		$(".edit_panel .edit_additional_rank").each(function() {
			var index = parseInt($(this).attr("data-index"), 10),
				value = (answers[index] !== undefined && answers[index] !== null) ? answers[index] : build_rank_default();
			set_rank_selects($(this), value);
		});

		$(".edit_panel .edit_additional_slider").each(function() {
			var slider = $(this),
				start_value = parseInt(slider.attr("data-value"), 10);

			slider.slider({
				max: 5,
				min: 1,
				step: 1,
				value: start_value,
				slide: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				},
				change: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				}
			});
		});
	}

	function open_additional_edit_panel(proband_id, task_id) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref) {
			return false;
		}
		render_additional_edit_panel(proband_id, task_id, ref.task);
		$(".edit_panel").show();
		return true;
	}

	function render_embodiment_edit_panel(proband_id, task_id, task) {
		var answers = (task.embodiment && task.embodiment.answers) ? task.embodiment.answers : [],
			html = "<h3>Edit System Usability Scale for " + format_proband_label(get_label_text(proband_id)) + " / " + get_label_text(task_id) + "</h3>";

		html += "<div class='edit_sliders'>";
		for (var i = 0; i < embodiment_questions.length; i++) {
			var answer_value = (answers[i] !== undefined) ? answers[i] : 3;
			if (answer_value < 1) {
				answer_value = 1;
			}
			if (answer_value > 5) {
				answer_value = 5;
			}

			html += "<section>";
			html += "<h4>" + embodiment_questions[i] + "</h4>";
			html += "<div class='slider edit_embodiment_slider' data-index='" + i + "' data-value='" + answer_value + "'></div>";
			html += "<p class='edit_rating_value'>Answer: <strong data-index='" + i + "'>" + answer_value + "</strong></p>";
			html += "</section>";
		}
		html += "</div>";
		html += "<p class='edit_error'></p>";
		html += "<button id='save_edit' type='button'>Save changes</button>";
		html += "<button id='cancel_edit' type='button'>Cancel</button>";

		$(".edit_panel").html(html);

		$(".edit_panel .edit_embodiment_slider").each(function() {
			var slider = $(this),
				start_value = parseInt(slider.attr("data-value"), 10);

			slider.slider({
				max: 5,
				min: 1,
				step: 1,
				value: start_value,
				slide: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				},
				change: function(event, ui) {
					var slider_index = $(this).data("index");
					$(".edit_rating_value strong[data-index='" + slider_index + "']").text(ui.value);
				}
			});
		});
	}

	function open_embodiment_edit_panel(proband_id, task_id) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref) {
			return false;
		}
		render_embodiment_edit_panel(proband_id, task_id, ref.task);
		$(".edit_panel").show();
		return true;
	}

	function close_edit_panel() {
		editing_pair_choices = null;
		editing_rating_scale = 100;
		$(".edit_panel").hide();
		$(".edit_panel").empty();
	}

	function show_task_results(proband_id, task_id, open_editor) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref || ref.task.tlx === undefined || ref.task.tlx === null) {
			return false;
		}

		if (ref.task.data && ref.task.data.pair_choices && $.isEmptyObject(ref.task.data.pair_choices)) {
			ref.task.data.pair_choices = derive_pair_choices_from_weights(ref.task.data.button_clicks || []);
		}

		var metrics = build_task_output(ref.task.data.slider_value, ref.task.data.button_clicks);
		$(".step_4 .results").html(metrics.output);

		if (open_editor) {
			open_edit_panel(proband_id, task_id);
		} else {
			close_edit_panel();
		}

		set_current_questionnaire("tlx");
		editing_target = {
			proband: proband_id,
			task: task_id,
			questionnaire: "tlx"
		};
		$("#edit_toggle").prop("disabled", false);
		return true;
	}

	function show_additional_results(proband_id, task_id, open_editor) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref || !ref.task.additional || !ref.task.additional.answers || !ref.task.additional.answers.length) {
			return false;
		}

		var output = build_additional_output(ref.task.additional.answers);
		$(".step_4 .results").html(output);

		if (open_editor) {
			open_additional_edit_panel(proband_id, task_id);
		} else {
			close_edit_panel();
		}

		set_current_questionnaire("additional");
		editing_target = {
			proband: proband_id,
			task: task_id,
			questionnaire: "additional"
		};
		$("#edit_toggle").prop("disabled", false);
		return true;
	}

	function show_embodiment_results(proband_id, task_id, open_editor) {
		var ref = get_task_reference(proband_id, task_id);
		if (!ref || !has_completed_embodiment_data(ref.task)) {
			return false;
		}

		var output = build_embodiment_output(ref.task.embodiment.answers);
		$(".step_4 .results").html(output);

		if (open_editor) {
			open_embodiment_edit_panel(proband_id, task_id);
		} else {
			close_edit_panel();
		}

		set_current_questionnaire("embodiment");
		editing_target = {
			proband: proband_id,
			task: task_id,
			questionnaire: "embodiment"
		};
		$("#edit_toggle").prop("disabled", false);
		return true;
	}

	function render_info(target_selector, proband_label, task_label) {
		$(".info").remove();
		$("<ul class='info'><li><strong>Participant:</strong> " + format_proband_label(proband_label) + "</li><li><strong>Task:</strong> " + task_label + "</li></ul>").insertAfter(target_selector + " h2");
	}

	function init_sliders(initial_values) {
		$(".step_2 .slider").each(function(i) {
			var start_value = (initial_values && initial_values[i] !== undefined) ? initial_values[i] : 50;

			if ($(this).hasClass("ui-slider")) {
				$(this).slider("destroy");
			}

			$(this)
				.data("index", i)
				.slider({
					max: 100,
					min: 1,
					step: 5,
					value: start_value,
					slide: function(event, ui) {
						var index = $(this).data("index");
						data_object["slider_value"][index] = ui.value;
					},
					stop: function(event, ui) {
						var index = $(this).data("index");
						data_object["slider_value"][index] = ui.value;
						set_progress_entry(settings[0], settings[2], {
							proband: settings[0],
							task: settings[2],
							step: 2,
							data_object: data_object,
							counter: 0,
							pairs_length: 0,
							random_pairs: null,
							started: false
						}, "tlx");
						save_state();
					}
				});

			data_object["slider_value"][i] = start_value;
		});
	}

	function render_step3_pair() {
		if (pairs_length) {
			$(".step_3 div").html("<button class='" + random_pairs[counter][0][0] + "'>" + random_pairs[counter][0][1] + "</button> or " + "<button class='" + random_pairs[counter][1][0] + "'>" + random_pairs[counter][1][1] + "</button>");
			if ( !$(".step_3").find(".to_go").length ) {
				$(".step_3").append("<p class='highlight to_go'></p>");
			}
			$(".step_3 .to_go").html("<strong>" + pairs_length + "</strong> to go!");
		}
	}

	function build_additional_output(answers) {
		var output = "<table><thead><tr><th>Question</th><th>Answer</th></tr></thead><tbody>";

		for (var i = 0; i < additional_questions.length; i++) {
			var answer_value = (answers && answers[i] !== undefined && answers[i] !== null) ? answers[i] : "";
			var display_value = is_additional_rank_question(i) ? format_rank_answer(answer_value) : answer_value;
			output += "<tr><td>" + escape_html(additional_questions[i]) + "</td><td>" + escape_html(display_value) + "</td></tr>";
		}

		output += "</tbody></table>";
		return output;
	}

	function build_embodiment_output(answers) {
		var output = "<table><thead><tr><th>Question</th><th>Answer</th></tr></thead><tbody>";

		for (var i = 0; i < embodiment_questions.length; i++) {
			var answer_value = (answers && answers[i] !== undefined && answers[i] !== null) ? answers[i] : "";
			output += "<tr><td>" + escape_html(embodiment_questions[i]) + "</td><td>" + escape_html(answer_value) + "</td></tr>";
		}

		output += "</tbody></table>";
		return output;
	}

	function init_additional_sliders(initial_answers) {
		$(".additional_slider").each(function(i) {
			var index = parseInt($(this).attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			var start_value = (initial_answers && initial_answers[index] !== undefined) ? initial_answers[index] : 3;
			start_value = parseInt(start_value, 10);
			if (isNaN(start_value)) {
				start_value = 3;
			}
			if (start_value < 1) {
				start_value = 1;
			}
			if (start_value > 5) {
				start_value = 5;
			}

			if ($(this).hasClass("ui-slider")) {
				$(this).slider("destroy");
			}

			$(this)
				.data("index", index)
				.slider({
					max: 5,
					min: 1,
					step: 1,
					value: start_value,
					stop: function(event, ui) {
						var index = $(this).data("index");
						additional_data.answers[index] = ui.value;
						set_progress_entry(settings[0], settings[2], {
							proband: settings[0],
							task: settings[2],
							step: "additional",
							additional_data: additional_data
						}, "additional");
						save_state();
					}
				});

			additional_data.answers[index] = start_value;
		});
	}

	function init_additional_text_inputs(initial_answers) {
		$(".additional_text").each(function(i) {
			var input = $(this),
				index = parseInt(input.attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			var start_value = (initial_answers && initial_answers[index] !== undefined && initial_answers[index] !== null)
				? initial_answers[index]
				: "";
			input.val(start_value);
			input.off("input.additional change.additional");
			input.on("input.additional change.additional", function() {
				if (!additional_data) {
					return;
				}
				additional_data.answers[index] = input.val();
				set_progress_entry(settings[0], settings[2], {
					proband: settings[0],
					task: settings[2],
					step: "additional",
					additional_data: additional_data
				}, "additional");
				save_state();
			});
		});
	}

	function init_additional_choice_inputs(initial_answers) {
		$(".additional_choice").each(function(i) {
			var container = $(this),
				index = parseInt(container.attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			var start_value = (initial_answers && initial_answers[index] !== undefined && initial_answers[index] !== null)
				? initial_answers[index]
				: "";
			container.find("input[type='radio']").prop("checked", false);
			if (start_value) {
				container.find("input[type='radio']").filter(function() {
					return $(this).val() === start_value;
				}).prop("checked", true);
			}
			container.find("input[type='radio']").off("change.additional_choice");
			container.find("input[type='radio']").on("change.additional_choice", function() {
				if (!additional_data) {
					return;
				}
				additional_data.answers[index] = container.find("input[type='radio']:checked").val() || "";
				set_progress_entry(settings[0], settings[2], {
					proband: settings[0],
					task: settings[2],
					step: "additional",
					additional_data: additional_data
				}, "additional");
				save_state();
			});
		});
	}

	function init_additional_rank_inputs(initial_answers) {
		$(".additional_rank").each(function(i) {
			var container = $(this),
				index = parseInt(container.attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			var start_value = (initial_answers && initial_answers[index] !== undefined && initial_answers[index] !== null)
				? initial_answers[index]
				: build_rank_default();
			set_rank_selects(container, start_value);
			container.find("select").off("change.additional_rank");
			container.find("select").on("change.additional_rank", function() {
				if (!additional_data) {
					return;
				}
				additional_data.answers[index] = collect_rank_answer(container);
				set_progress_entry(settings[0], settings[2], {
					proband: settings[0],
					task: settings[2],
					step: "additional",
					additional_data: additional_data
				}, "additional");
				save_state();
			});
		});
	}

	function init_embodiment_sliders(initial_answers) {
		$(".embodiment_slider").each(function(i) {
			var start_value = (initial_answers && initial_answers[i] !== undefined) ? initial_answers[i] : 3;

			if ($(this).hasClass("ui-slider")) {
				$(this).slider("destroy");
			}

			$(this)
				.data("index", i)
				.slider({
					max: 5,
					min: 1,
					step: 1,
					value: start_value,
					stop: function(event, ui) {
						var index = $(this).data("index");
						embodiment_data.answers[index] = ui.value;
						set_progress_entry(settings[0], settings[2], {
							proband: settings[0],
							task: settings[2],
							step: "embodiment",
							embodiment_data: embodiment_data
						}, "embodiment");
						save_state();
					}
				});

			embodiment_data.answers[i] = start_value;
		});
	}

	function enter_additional(proband_label, task_label, progress_entry) {
		additional_data = ensure_additional_data(progress_entry ? progress_entry.additional_data : null);

		init_additional_sliders(additional_data.answers);
		init_additional_text_inputs(additional_data.answers);
		init_additional_choice_inputs(additional_data.answers);
		init_additional_rank_inputs(additional_data.answers);

		set_progress_entry(settings[0], settings[2], {
			proband: settings[0],
			task: settings[2],
			step: "additional",
			additional_data: additional_data
		}, "additional");
		save_state();

		$(".step_1").hide();
		$(".step_2").hide();
		$(".step_3").hide();
		$(".step_embodiment").hide();
		$(".step_additional").show();
		set_current_questionnaire("additional");
		render_info(".step_additional", proband_label, task_label);

		push_history_state({
			view: "additional",
			questionnaire: "additional",
			proband: settings[0],
			task: settings[2]
		});
	}

	function enter_embodiment(proband_label, task_label, progress_entry) {
		embodiment_data = ensure_embodiment_data(progress_entry ? progress_entry.embodiment_data : null);

		init_embodiment_sliders(embodiment_data.answers);

		set_progress_entry(settings[0], settings[2], {
			proband: settings[0],
			task: settings[2],
			step: "embodiment",
			embodiment_data: embodiment_data
		}, "embodiment");
		save_state();

		$(".step_1").hide();
		$(".step_2").hide();
		$(".step_3").hide();
		$(".step_additional").hide();
		$(".step_embodiment").show();
		set_current_questionnaire("embodiment");
		render_info(".step_embodiment", proband_label, task_label);

		push_history_state({
			view: "embodiment",
			questionnaire: "embodiment",
			proband: settings[0],
			task: settings[2]
		});
	}

	function enter_step2(proband_label, task_label, progress_entry) {
		data_object = ensure_data_object(progress_entry ? progress_entry.data_object : null);
		data_object.rating_scale = 100;

		init_sliders(data_object["slider_value"]);

		set_progress_entry(settings[0], settings[2], {
			proband: settings[0],
			task: settings[2],
			step: 2,
			data_object: data_object,
			counter: 0,
			pairs_length: 0,
			random_pairs: null,
			started: false
		}, "tlx");
		save_state();

		$(".step_1").hide();
		$(".step_2").show();
		set_current_questionnaire("tlx");
		render_info(".step_2", proband_label, task_label);

		push_history_state({
			view: "step2",
			questionnaire: "tlx",
			proband: settings[0],
			task: settings[2]
		});
	}

	function enter_step3(proband_label, task_label, progress_entry) {
		var entry = normalize_progress(progress_entry);

		if (!entry || !entry.random_pairs || !entry.random_pairs.length) {
			return false;
		}

		data_object = ensure_data_object(entry.data_object);
		random_pairs = entry.random_pairs;
		counter = entry.counter;
		pairs_length = entry.pairs_length;

		if ( $(".step_3").find("div").length ) {
			$(".step_3 div").html("<button>Start</button>");
		} else {
			$(".step_3").append("<div><button>Start</button></div>");
		}
		$(".step_3 .to_go").remove();

		if (entry.started) {
			render_step3_pair();
		}

		set_progress_entry(settings[0], settings[2], entry, "tlx");
		save_state();

		$(".step_1").hide();
		$(".step_2").hide();
		$(".step_3").show();
		set_current_questionnaire("tlx");
		render_info(".step_3", proband_label, task_label);
		push_history_state({
			view: "step3",
			questionnaire: "tlx",
			proband: settings[0],
			task: settings[2],
			progress: {
				data_object: data_object,
				random_pairs: random_pairs,
				counter: counter,
				pairs_length: pairs_length,
				started: entry.started
			}
		});
		return true;
	}

	function serialize_lists() {
		var probands = [],
			tasks = [];

		$(".step_1 .first .list label").each(function() {
			probands.push({
				id: $(this).attr("for"),
				label: $(this).html()
			});
		});

		$(".step_1 .second .list label").each(function() {
			tasks.push({
				id: $(this).attr("for"),
				label: $(this).html()
			});
		});

		return {
			probands: probands,
			tasks: tasks
		};
	}

	function apply_saved_lists(state) {
		if (state.probands && state.probands.length) {
			var proband_container = $(".step_1 .first .list > :first-child");
			proband_container.empty();
			$.each(state.probands, function(i, item) {
				if (!item || !item.id) {
					return;
				}
					proband_container.append(
						"<div><input type='radio' name='probands' id='" + item.id + "'" + (i === 0 ? " checked" : "") + "> <label class='proband-name' for='" + item.id + "'>" + item.label + "</label> <button class='edit_proband' type='button' data-proband='" + item.id + "'>Edit</button> <button class='delete_proband' type='button' data-proband='" + item.id + "'>Delete</button></div>"
					);
			});
		}

		if (state.tasks && state.tasks.length) {
			var task_container = $(".step_1 .second .list > :first-child");
			task_container.empty();
			$.each(state.tasks, function(i, item) {
				if (!item || !item.id) {
					return;
				}
				task_container.append(
					"<div><input type='radio' name='tasks' id='" + item.id + "'" + (i === 0 ? " checked" : "") + "> <label for='" + item.id + "'>" + item.label + "</label> <button class='delete_task' type='button' data-task='" + item.id + "'>Delete</button></div>"
				);
			});
		}

		refresh_review_options();
	}

	function save_state() {
		if (!window.localStorage || !window.JSON) {
			return;
		}
		var lists = serialize_lists(),
			payload = {
				version: 1,
				probands: lists.probands,
				tasks: lists.tasks,
				final_result: final_result,
				in_progress: in_progress
			};

		try {
			localStorage.setItem(storage_key, JSON.stringify(payload));
		} catch (error) {
			return;
		}
	}

	function build_table_output() {
		var tasks = get_task_list(),
			output = "<thead><tr><th rowspan='2'>Participants</th>";

		for (var t = 0; t < tasks.length; t++) {
			output += "<th colspan='3'>" + tasks[t].label + "</th>";
		}

		output += "<th rowspan='2'>Actions</th></tr><tr>";
		for (var h = 0; h < tasks.length; h++) {
			output += "<th>TLX</th><th>SUS</th><th>Additional</th>";
		}

		output += "</tr></thead><tbody>";

		for (var i = 0; i < final_result.length; i++) {
			var task_lookup = {};
			for (var j = 0; j < final_result[i].tasks.length; j++) {
				task_lookup[final_result[i].tasks[j].name] = final_result[i].tasks[j];
			}

			output += "<tr><th>" + format_proband_label(get_label_text(final_result[i].proband)) + "</th>";
			for (var k = 0; k < tasks.length; k++) {
				var task = task_lookup[tasks[k].id],
					tlx_done = task && task.tlx !== undefined && task.tlx !== null,
					additional_done = task && task.additional && task.additional.answers && task.additional.answers.length,
					embodiment_done = has_completed_embodiment_data(task),
					no_questionnaire_answered = !tlx_done && !additional_done && !embodiment_done,
					empty_status_attr = no_questionnaire_answered ? " class='status-empty'" : "",
					tlx_attr = tlx_done ? " data-tlx='" + task.tlx + "'" : "";

				output += "<td" + empty_status_attr + tlx_attr + ">" + status_label(tlx_done) + "</td>";
				output += "<td" + empty_status_attr + ">" + status_label(embodiment_done) + "</td>";
				output += "<td" + empty_status_attr + ">" + status_label(additional_done) + "</td>";
			}
			output += "<td><button class='delete_proband_row' type='button' data-proband='" + final_result[i].proband + "'>Delete</button></td>";
		}

		return output;
	}

	function render_overview() {
		$(".step_0 p").remove();
		tableoutput = build_table_output();

		if ($(".step_0 table").length) {
			$(".step_0 table").html(tableoutput);
		} else {
			$("<table class='test'>" + tableoutput + "</tbody></table>").insertAfter('.step_0 h2');
		}

		var tasks = get_task_list(),
			task_stats = [];

		for (var i = 0; i < tasks.length; i++) {
			var values = [];
			for (var j = 0; j < final_result.length; j++) {
				for (var k = 0; k < final_result[j].tasks.length; k++) {
					if (final_result[j].tasks[k].name === tasks[i].id) {
						var tlx_value = final_result[j].tasks[k].tlx;
						if (tlx_value !== undefined && tlx_value !== null) {
							values.push(tlx_value);
						}
						break;
					}
				}
			}

			if (values.length) {
				var total = 0;
				for (var v = 0; v < values.length; v++) {
					total += values[v];
				}
				var avg = total / values.length,
					variance = 0;
				for (var d = 0; d < values.length; d++) {
					variance += Math.pow(values[d] - avg, 2);
				}
				var sd = Math.sqrt(variance).toFixed(2),
					avg_display = parseFloat(avg.toFixed(2));

				task_stats.push({
					label: tasks[i].label,
					avg: avg_display,
					sd: parseFloat(sd)
				});
			} else {
				task_stats.push({
					label: tasks[i].label,
					avg: null,
					sd: null
				});
			}
		}

		var min_array = [],
			max_array = [],
			avg_array = [],
			label_array = [];

		for (var s = 0; s < task_stats.length; s++) {
			if (task_stats[s].avg === null || task_stats[s].sd === null) {
				continue;
			}
			label_array.push(task_stats[s].label);
			min_array.push(+parseFloat((task_stats[s].avg - task_stats[s].sd).toFixed(2)).toFixed(2));
			max_array.push(+parseFloat((task_stats[s].avg + task_stats[s].sd).toFixed(2)).toFixed(2));
			avg_array.push(+parseFloat(task_stats[s].avg).toFixed(2));
		}

		if (min_array.length > 1) {
			var chart,
				options = {
					chart: {
						animation: true,
						defaultSeriesType: "line",
						renderTo: "container"
					},
					credits: {
						enabled: false
					},
					title: {
						text: ""
					},
					tooltip: {
						borderWidth: 1,
						headerFormat: '<b>{point.key}</b><br>',
						pointFormat: '<div><span style="color: {series.color}">{series.name}:</span> {point.y}</div>',
						useHTML: true,
						crosshairs: true,
						shared: true
					},
					legend: {
						layout: 'vertical',
						align: 'right',
						verticalAlign: 'middle',
						x: 0,
						y: 0,
						borderWidth: 0
					},
					plotOptions: {
						series: {
							shadow: false,
							lineWidth: 1,
							marker: {
								enabled: false,
								symbol: 'circle',
								radius: 1,
								states: {
									hover: {
										enabled: true
									}
								}
							}
						}
					},
					xAxis: {
						categories: label_array,
						tickmarkPlacement: 'on',
						labels: {
							y: 20
						},
						title: {
							text: 'Tasks',
							margin: 10
						}
					},
					yAxis: {
						title: {
							text: 'TLX score',
							margin: 10
						},
						min: null,
						startOnTick: false
					},
					series: [{
						name: 'Max. deviation',
						data: max_array
					}, {
						name: 'Average TLX',
						data: avg_array,
						lineWidth: 2
					}, {
						name: 'Min. deviation',
						data: min_array
					}]
				};

			chart = new Highcharts.Chart(options);
		}
	}

	function delete_proband_data(proband_id) {
		for (var i = final_result.length - 1; i >= 0; i--) {
			if (final_result[i].proband === proband_id) {
				final_result.splice(i, 1);
				break;
			}
		}

		for (var key in in_progress) {
			if (in_progress.hasOwnProperty(key) && key.indexOf(proband_id + "|") === 0) {
				delete in_progress[key];
			}
		}

		if (editing_target && editing_target.proband === proband_id) {
			editing_target = null;
			close_edit_panel();
			$("#edit_toggle").prop("disabled", true);
		}

		save_state();
		refresh_review_options();
		update_export_state();

		if (has_exportable_data()) {
			render_overview();
		} else {
			show_empty_overview();
		}
	}

	function remove_proband_from_list(proband_id) {
		$(".step_1 .first .list input[id='" + proband_id + "']").closest("div").remove();
		var first_proband = $(".step_1 .first .list input[type='radio']").first();
		if (first_proband.length) {
			first_proband.prop("checked", true);
		}

		save_state();
		refresh_review_options();
		update_export_state();
	}

	function rename_proband(proband_id, next_id, next_label) {
		var row = $(".step_1 .first .list input[id='" + proband_id + "']").closest("div"),
			input = row.find("input[name='probands']"),
			was_selected = input.is(":checked"),
			pending_progress = {};

		if (!row.length || !input.length) {
			return;
		}

		input.attr("id", next_id);
		row.find("label.proband-name").attr("for", next_id).html(next_label);
		row.find(".delete_proband").attr("data-proband", next_id);
		row.find(".edit_proband").attr("data-proband", next_id);

		for (var i = 0; i < final_result.length; i++) {
			if (final_result[i].proband === proband_id) {
				final_result[i].proband = next_id;
			}
		}

		for (var key in in_progress) {
			if (!in_progress.hasOwnProperty(key)) {
				continue;
			}
			var parts = key.split("|");
			if (parts.length !== 3 || parts[0] !== proband_id) {
				continue;
			}
			pending_progress[next_id + "|" + parts[1] + "|" + parts[2]] = in_progress[key];
			delete in_progress[key];
		}

		for (var pending_key in pending_progress) {
			if (pending_progress.hasOwnProperty(pending_key)) {
				in_progress[pending_key] = pending_progress[pending_key];
			}
		}

		if (settings && settings.length >= 2 && settings[0] === proband_id) {
			settings[0] = next_id;
			settings[1] = next_label;
		}

		if (editing_target && editing_target.proband === proband_id) {
			editing_target.proband = next_id;
		}

		if (was_selected) {
			input.prop("checked", true);
		}
	}

	function show_empty_overview() {
		$(".step_0 table").remove();
		$(".step_0 p").remove();
		$("<p>No data available yet.</p>").insertAfter(".step_0 h2");
		$("#container").empty();
	}

	function update_edit_weights_display() {
		if (!editing_pair_choices) {
			return;
		}
		var weights = compute_weights_from_pairs(editing_pair_choices);
		for (var i = 0; i < weights.length; i++) {
			$(".edit_weight_value[data-index='" + i + "']").text(weights[i]);
		}
	}

	function restore_state() {
		if (!window.localStorage || !window.JSON) {
			return;
		}
		var raw = localStorage.getItem(storage_key),
			state = raw ? safe_parse_json(raw) : null;

		if (!state) {
			return;
		}

		if (state.tasks) {
			state.tasks = sanitize_tasks_list(state.tasks);
		} else {
			state.tasks = sanitize_tasks_list([]);
		}

		if (state.probands || state.tasks) {
			apply_saved_lists(state);
		}

		if (state.final_result && $.isArray(state.final_result)) {
			final_result = state.final_result;
		}

		if (state.in_progress && typeof state.in_progress === "object") {
			in_progress = state.in_progress;
			for (var key in in_progress) {
				if (in_progress.hasOwnProperty(key)) {
					var parts = key.split("|");
					if (parts.length === 2) {
						in_progress[key + "|tlx"] = in_progress[key];
						delete in_progress[key];
					}
				}
			}
		} else {
			in_progress = {};
		}

		prune_removed_tasks();

		for (var i = 0; i < final_result.length; i++) {
			for (var j = 0; j < final_result[i].tasks.length; j++) {
				if (final_result[i].tasks[j].tlx !== undefined && final_result[i].tasks[j].tlx !== null) {
					clear_progress_entry(final_result[i].proband, final_result[i].tasks[j].name, "tlx");
				}
				if (final_result[i].tasks[j].additional && final_result[i].tasks[j].additional.answers && final_result[i].tasks[j].additional.answers.length) {
					clear_progress_entry(final_result[i].proband, final_result[i].tasks[j].name, "additional");
				}
				if (has_completed_embodiment_data(final_result[i].tasks[j])) {
					clear_progress_entry(final_result[i].proband, final_result[i].tasks[j].name, "embodiment");
				}
			}
		}

		if (has_exportable_data()) {
			$(".step_0 p").remove();
			render_overview();
		}
		update_export_state();
		save_state();
	}

	function build_csv_export() {
		if (!has_exportable_data()) {
			return "";
		}

		var rows = [],
			header = [
				"Participant ID",
				"Participant",
				"Task ID",
				"Task",
				"TLX Score"
			];

		for (var h = 0; h < demands.length; h++) {
			header.push(demands[h][1] + " rating");
			header.push(demands[h][1] + " weight");
			header.push(demands[h][1] + " product");
		}

		header.push("Product sum");
		header.push("Weight sum");
		for (var q = 0; q < additional_questions.length; q++) {
			header.push("Additional Q" + (q + 1));
		}
		for (var e = 0; e < embodiment_questions.length; e++) {
			header.push("SUS Q" + (e + 1));
		}

		rows.push(header);

		for (var i = 0; i < final_result.length; i++) {
			var proband_id = final_result[i].proband,
				proband_name = get_label_text(proband_id);

			for (var j = 0; j < final_result[i].tasks.length; j++) {
				var task = final_result[i].tasks[j],
					task_id = task.name,
					task_name = get_label_text(task_id),
					data = task.data || {},
					ratings = data.slider_value || [],
					weights = data.button_clicks || [],
					sum = "",
					weight_sum = "",
					tlx_score = (task.tlx !== undefined && task.tlx !== null) ? task.tlx : "",
					additional_answers = (task.additional && task.additional.answers) ? task.additional.answers : [],
					embodiment_answers = has_completed_embodiment_data(task) ? task.embodiment.answers : [];

				if (task.tlx === undefined || task.tlx === null) {
					if (!additional_answers.length && !embodiment_answers.length) {
					continue;
					}
				}

				if (ratings.length && weights.length) {
					sum = 0;
					weight_sum = 0;
					for (var k = 0; k < demands.length; k++) {
						if (ratings[k] !== undefined && weights[k] !== undefined) {
							sum += ratings[k] * weights[k];
							weight_sum += weights[k];
						}
					}
					if (weight_sum) {
						tlx_score = Math.round(sum / weight_sum);
					}
				}

				var row = [
					proband_id,
					proband_name,
					task_id,
					task_name,
					tlx_score
				];

				for (var m = 0; m < demands.length; m++) {
					var rating = ratings[m],
						weight = weights[m],
						product = (rating !== undefined && weight !== undefined) ? rating * weight : "";
					row.push((rating !== undefined) ? rating : "");
					row.push((weight !== undefined) ? weight : "");
					row.push(product);
				}

				row.push(sum);
				row.push(weight_sum);
				for (var a = 0; a < additional_questions.length; a++) {
					var additional_value = (additional_answers[a] !== undefined) ? additional_answers[a] : "";
					if (is_additional_rank_question(a)) {
						additional_value = format_rank_answer(additional_value);
					}
					row.push(additional_value);
				}
				for (var b = 0; b < embodiment_questions.length; b++) {
					row.push((embodiment_answers[b] !== undefined) ? embodiment_answers[b] : "");
				}
				rows.push(row);
			}
		}

		return $.map(rows, function(row) {
			return $.map(row, csv_escape).join(",");
		}).join("\r\n");
	}

	/* hide future steps */

	$(".step_1, .step_2, .step_3, .step_4, .step_additional, .step_embodiment").hide();

	$("<p>No data available yet.</p>").insertAfter(".step_0 h2");
	restore_state();
	refresh_review_options();
	update_export_state();
	$("#edit_toggle").prop("disabled", true);
	set_page_title("overview");

	$("input[name='questionnaire']").change(function() {
		set_current_questionnaire($(this).val());
	});

	/* step 0 */

	$("#go_step_1").click(function() {
		$(".step_0").hide();
		$(".step_1").show();
		set_page_title("step1");
		push_history_state({
			view: "step1",
			questionnaire: current_questionnaire
		});
	});

	$("#export_csv").click(function() {
		var csv = build_csv_export();
		if (!csv) {
			alert("No completed data to export yet.");
			return;
		}

		var now = new Date(),
			date_stamp = now.getFullYear() + "-" + pad2(now.getMonth() + 1) + "-" + pad2(now.getDate()) + "-" +
				pad2(now.getHours()) + "-" + pad2(now.getMinutes()) + "-" + pad2(now.getSeconds()),
			filename = "nasa_tlx_export_" + date_stamp + ".csv",
			blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });

		if (window.navigator && window.navigator.msSaveBlob) {
			window.navigator.msSaveBlob(blob, filename);
			return;
		}

		var url = URL.createObjectURL(blob),
			link = document.createElement("a");

		link.setAttribute("href", url);
		link.setAttribute("download", filename);
		link.style.display = "none";
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		setTimeout(function() {
			URL.revokeObjectURL(url);
		}, 1000);
	});

	$("#review_data").click(function() {
		var proband_id = $("#review_proband").val(),
			task_id = $("#review_task").val(),
			review_type = $("#review_type").val() || "tlx";

		$(".review_error").text("");

		if (!proband_id || !task_id) {
			$(".review_error").text("Please select a participant and a task.");
			return;
		}

		set_current_questionnaire(review_type);

		if (review_type === "additional") {
			if (!show_additional_results(proband_id, task_id, true)) {
				$(".review_error").text("No completed additional data found for this participant/task.");
				return;
			}
		} else if (review_type === "embodiment") {
			if (!show_embodiment_results(proband_id, task_id, true)) {
				$(".review_error").text("No completed SUS data found for this participant/task.");
				return;
			}
		} else {
			if (!show_task_results(proband_id, task_id, true)) {
				$(".review_error").text("No completed data found for this participant/task.");
				return;
			}
		}

		$(".step_0, .step_1, .step_2, .step_3, .step_additional, .step_embodiment").hide();
		$(".step_4").show();
		push_history_state({
			view: "results",
			questionnaire: review_type,
			proband: proband_id,
			task: task_id
		});
	});

	$(document).on("click", ".delete_proband_row", function() {
		var proband_id = $(this).attr("data-proband");
		if (!proband_id) {
			return;
		}

		var proband_name = get_label_text(proband_id);
		if (!window.confirm("Delete all recorded data for participant \"" + proband_name + "\"? The participant will remain in the list.")) {
			return;
		}

		delete_proband_data(proband_id);
	});

	$(document).on("click", ".delete_task", function(event) {
		event.preventDefault();
		var task_id = $(this).attr("data-task");
		if (!task_id) {
			return;
		}

		var task_name = get_label_text(task_id);
		if (!window.confirm("Remove task \"" + task_name + "\" from the list? Recorded results will remain.")) {
			return;
		}

		delete_task_data(task_id);
	});

	$(document).on("click", ".delete_proband", function(event) {
		event.preventDefault();
		var proband_id = $(this).attr("data-proband");
		if (!proband_id) {
			return;
		}

		var proband_name = get_label_text(proband_id);
		if (!window.confirm("Remove participant \"" + proband_name + "\" from the list? Recorded results will remain.")) {
			return;
		}

		remove_proband_from_list(proband_id);
	});

	$(document).on("click", ".edit_proband", function(event) {
		event.preventDefault();
		var proband_id = $(this).attr("data-proband");
		if (!proband_id) {
			return;
		}

		var current_label = get_label_text(proband_id),
			parsed = parse_participant_label(current_label),
			participant_name = window.prompt("Participant name:", parsed.name),
			camipro_number,
			next_label,
			next_id;

		if (participant_name === null) {
			return;
		}
		participant_name = $.trim(participant_name.replace(/ +(?= )/g, ""));

		camipro_number = window.prompt("Camipro number:", parsed.camipro);
		if (camipro_number === null) {
			return;
		}
		camipro_number = $.trim(camipro_number.replace(/ +(?= )/g, ""));

		if (!participant_name || !camipro_number) {
			alert("Error. Please enter both participant name and Camipro number.");
			return;
		}

		next_label = build_participant_label(participant_name, camipro_number);
		next_id = build_participant_id(participant_name, camipro_number);

		if (next_id !== proband_id && $(".step_1 .first .list input[id='" + next_id + "']").length) {
			alert("Error. This participant already exists.");
			return;
		}

		rename_proband(proband_id, next_id, next_label);
		save_state();
		refresh_review_options();
		update_export_state();
		if (has_exportable_data()) {
			render_overview();
		} else {
			show_empty_overview();
		}
	});

	$(document).on("click", ".edit_pair_option", function() {
		if (!editing_pair_choices) {
			return;
		}
		var pair = $(this).attr("data-pair"),
			choice = $(this).attr("data-choice");

		if (!pair || !choice) {
			return;
		}

		editing_pair_choices[pair] = choice;
		$(".edit_pair_option[data-pair='" + pair + "']").removeClass("selected");
		$(this).addClass("selected");
		update_edit_weights_display();
	});

	$("#edit_toggle").click(function() {
		if (!editing_target) {
			return;
		}
		if ($(".edit_panel").is(":visible")) {
			close_edit_panel();
			return;
		}
		if (editing_target.questionnaire === "additional") {
			open_additional_edit_panel(editing_target.proband, editing_target.task);
		} else if (editing_target.questionnaire === "embodiment") {
			open_embodiment_edit_panel(editing_target.proband, editing_target.task);
		} else {
			open_edit_panel(editing_target.proband, editing_target.task);
		}
	});

	$(document).on("click", "#cancel_edit", function() {
		close_edit_panel();
	});

	$(document).on("click", "#save_edit", function() {
		if (!editing_target) {
			return;
		}

		var ratings = [],
			weights = [],
			error_message = "";

		if (editing_target.questionnaire === "additional") {
			var answers = build_additional_defaults();

			$(".edit_panel .edit_additional_slider").each(function() {
				var index = parseInt($(this).attr("data-index"), 10),
					value = parseInt($(this).slider("value"), 10);

				if (isNaN(value) || value < 1 || value > 5) {
					error_message = "Answers must be between 1 and 5.";
					return false;
				}
				answers[index] = value;
			});

			$(".edit_panel .edit_additional_text").each(function() {
				var index = parseInt($(this).attr("data-index"), 10);
				if (isNaN(index)) {
					return;
				}
				answers[index] = $(this).val();
			});

			$(".edit_panel .edit_additional_choice").each(function() {
				var index = parseInt($(this).attr("data-index"), 10);
				if (isNaN(index)) {
					return;
				}
				answers[index] = $(this).find("input[type='radio']:checked").val() || "";
			});

			$(".edit_panel .edit_additional_rank").each(function() {
				var index = parseInt($(this).attr("data-index"), 10);
				if (isNaN(index)) {
					return;
				}
				answers[index] = collect_rank_answer($(this));
			});

			if (error_message) {
				$(".edit_panel .edit_error").text(error_message);
				return;
			}

			var additional_output = build_additional_output(answers),
				additional_ref = get_task_reference(editing_target.proband, editing_target.task);

			if (!additional_ref) {
				$(".edit_panel .edit_error").text("Could not find the selected record.");
				return;
			}

			additional_ref.task.additional = {
				answers: answers,
				output: additional_output
			};
			clear_progress_entry(editing_target.proband, editing_target.task, "additional");

			$(".step_4 .results").html(additional_output);
			save_state();
			update_export_state();
			render_overview();
			$(".edit_panel .edit_error").text("");
			return;
		}

		if (editing_target.questionnaire === "embodiment") {
			var embodiment_answers = [];

			$(".edit_panel .edit_embodiment_slider").each(function() {
				var index = parseInt($(this).attr("data-index"), 10),
					value = parseInt($(this).slider("value"), 10);

				if (isNaN(value) || value < 1 || value > 5) {
					error_message = "Answers must be between 1 and 5.";
					return false;
				}
				embodiment_answers[index] = value;
			});

			if (error_message) {
				$(".edit_panel .edit_error").text(error_message);
				return;
			}

			var embodiment_output = build_embodiment_output(embodiment_answers),
				embodiment_ref = get_task_reference(editing_target.proband, editing_target.task);

			if (!embodiment_ref) {
				$(".edit_panel .edit_error").text("Could not find the selected record.");
				return;
			}

			embodiment_ref.task.embodiment = {
				answers: embodiment_answers,
				output: embodiment_output
			};
			clear_progress_entry(editing_target.proband, editing_target.task, "embodiment");

			$(".step_4 .results").html(embodiment_output);
			save_state();
			update_export_state();
			render_overview();
			$(".edit_panel .edit_error").text("");
			return;
		}

		$(".edit_panel .edit_slider").each(function() {
			var index = parseInt($(this).attr("data-index"), 10),
				value = parseInt($(this).slider("value"), 10);

			if (isNaN(value) || value < 1 || value > 20) {
				error_message = "Ratings must be between 1 and 20.";
				return false;
			}
			ratings[index] = value * (editing_rating_scale / 20);
		});

		if (!error_message) {
			if (!editing_pair_choices || $.isEmptyObject(editing_pair_choices)) {
				error_message = "Please select a value for each pair.";
			} else {
				weights = compute_weights_from_pairs(editing_pair_choices);
			}
		}

		if (error_message) {
			$(".edit_panel .edit_error").text(error_message);
			return;
		}

		var metrics = build_task_output(ratings, weights);
		if (!metrics.weight_sum) {
			$(".edit_panel .edit_error").text("Total weights must be greater than 0.");
			return;
		}

		var ref = get_task_reference(editing_target.proband, editing_target.task);
		if (!ref) {
			$(".edit_panel .edit_error").text("Could not find the selected record.");
			return;
		}

		ref.task.data = {
			slider_value: ratings,
			button_clicks: weights,
			pair_choices: editing_pair_choices,
			rating_scale: editing_rating_scale
		};
		ref.task.tlx = metrics.tlx;
		ref.task.output = metrics.output;
		clear_progress_entry(editing_target.proband, editing_target.task, "tlx");

		$(".step_4 .results").html(metrics.output);
		save_state();
		update_export_state();
		render_overview();
		$(".edit_panel .edit_error").text("");
	});

	/* step 1 */

	$(".step_1 input[type='submit']").live("click", function() {

		// remove error paragraphs at first (if proband error is shown and error occurs on task, the proband error disappears)
		$(".step_1 .cf p").remove();

		var form = $(this).closest("form"),
			section = form.parent(),
			subject = (section.hasClass("first")) ? "proband" : "task",
			subject_label = (section.hasClass("first")) ? "participant" : "task",
			value = "",
			formatted_value = "",
			proband_exists = false,
			error_message = "";

		if (subject === "proband") {
			var participant_name = $.trim(form.find("#create_proband_name").val().replace(/ +(?= )/g, '')),
				camipro_number = $.trim(form.find("#create_proband_camipro").val().replace(/ +(?= )/g, ''));

			if (!participant_name || !camipro_number) {
				error_message += "Error. Please enter both participant name and Camipro number.";
			} else {
				value = build_participant_label(participant_name, camipro_number);
				formatted_value = build_participant_id(participant_name, camipro_number);
			}
		} else {
			value = $.trim(form.find("input[type='text']").first().val().replace(/ +(?= )/g, ''));
			formatted_value = value.toLowerCase().split(' ').join('_');
		}

		// check if proband already exists
		section.find(".list label").each(function() {
			if ($(this).html().toLowerCase() === value.toLowerCase()) {
				proband_exists = true;
			}
			return;
		});

		// if input has an actual character in it
		if (!error_message) {
			if (value) {
				if (proband_exists) {
					error_message += "Error. This " + subject_label + " already exists.";
				} else {
					var label_class = (subject === "proband") ? " class='proband-name'" : "",
						entry_markup = "<div><input type='radio' name='" + subject + "s' id='" + formatted_value + "'> <label" + label_class + " for='" + formatted_value + "'>" + value + "</label>";
						if (subject === "task") {
							entry_markup += " <button class='delete_task' type='button' data-task='" + formatted_value + "'>Delete</button>";
						} else if (subject === "proband") {
							entry_markup += " <button class='edit_proband' type='button' data-proband='" + formatted_value + "'>Edit</button>";
							entry_markup += " <button class='delete_proband' type='button' data-proband='" + formatted_value + "'>Delete</button>";
						}
					entry_markup += "</div>";
					$(entry_markup).appendTo(section.find(".list >:first-child"));
					// reset value of input after proband or task was created
					form.find("input[type='text']").val("");
					save_state();
					refresh_review_options();
				}
			} else {
				error_message += "Error. No characters entered.";
			}
		}

		if ( error_message ) {
			form.append("<p class='error'>" + error_message + "</p>");
		}
		return false;
	});

	$(".step_1 .go_back a").click(function() {
		$(".step_1 .cf p").remove();
		$(".step_1").hide();
		$(".step_0").show();
		set_page_title("overview");
		push_history_state({
			view: "overview",
			questionnaire: current_questionnaire
		});
		return false;
	});

	$("#step_1_continue").click(function() {
		settings = [];
		var proband_selection = $("input[name='probands']:checked");
		var task_selection = $("input[name='tasks']:checked");
		var questionnaire = $("input[name='questionnaire']:checked").val() || "tlx";
		set_current_questionnaire(questionnaire);

		// reset input values and thrown error paragraphs caused by input submits
		$(".step_1 input[type='text']").val("");
		$(".step_1 .cf p").remove();

		if (!proband_selection.length || !task_selection.length) {
			var selection_error = "Please select a participant and a task.";
			if (proband_selection.length && !task_selection.length) {
				selection_error = "Please select a task.";
			} else if (!proband_selection.length && task_selection.length) {
				selection_error = "Please select a participant.";
			}
			$(".step_1 .cf").append("<p class='error'>" + selection_error + "</p>");
			return false;
		}

		settings = [
			proband_selection.attr("id"),
			proband_selection.siblings("label").html(),
			task_selection.attr("id"),
			task_selection.siblings("label").html()
		];

		// check if proband already completed a task
		var proband_exists = false,
			task_exists = false,
			task_completed = false,
			additional_completed = false,
			embodiment_completed = false;

		// iterate probands
		for ( var i = 0, length = final_result.length; i < length; i++ ) {
			// if proband exists
			if ( final_result[i].proband === settings[0] ) {
				proband_exists = true;
				// iterate tasks
				for ( var j = 0, tasks_length = final_result[i].tasks.length; j < tasks_length; j++) {
					// if task exists
					if (final_result[i].tasks[j].name === settings[2]) {
						task_exists = true;
						task_completed = (final_result[i].tasks[j].tlx !== undefined && final_result[i].tasks[j].tlx !== null);
						additional_completed = (final_result[i].tasks[j].additional && final_result[i].tasks[j].additional.answers && final_result[i].tasks[j].additional.answers.length);
						embodiment_completed = has_completed_embodiment_data(final_result[i].tasks[j]);
						break;
					}
				}
				break;
			}
		}

		var progress_entry = normalize_progress(get_progress_entry(settings[0], settings[2], "tlx"));
		var additional_progress = get_progress_entry(settings[0], settings[2], "additional");
		var embodiment_progress = get_progress_entry(settings[0], settings[2], "embodiment");

		// if proband doesn’t exist make first push to array and continue to step 2
		if ( !proband_exists ) {
			final_result.push(
				{
					proband: settings[0],
					tasks: [
						{
							name: settings[2],
							data: {}
						}
					]
				}
			);
			save_state();
			if (questionnaire === "additional") {
				enter_additional(settings[1], settings[3], additional_progress);
			} else if (questionnaire === "embodiment") {
				enter_embodiment(settings[1], settings[3], embodiment_progress);
			} else {
				enter_step2(settings[1], settings[3], null);
			}
		} else {
			// if proband didn’t complete the task make push to tasks array and continue to step 2
			if (!task_exists) {
				final_result[i].tasks.push(
					{
						name: settings[2],
						data: {}
					}
				);
				save_state();
				if (questionnaire === "additional") {
					enter_additional(settings[1], settings[3], additional_progress);
				} else if (questionnaire === "embodiment") {
					enter_embodiment(settings[1], settings[3], embodiment_progress);
				} else {
					enter_step2(settings[1], settings[3], null);
				}
			} else if (questionnaire === "additional") {
				if (additional_completed) {
					var additional_error = "Participant <strong>" + format_proband_label(settings[1]) + "</strong> already answered additional questions for task <strong>" + settings[3] + "</strong>.";
					if($(".step_1 .cf > .error").length) {
						$(".step_1 .cf > .error").html(additional_error);
					} else {
						$(".step_1 .cf").append("<p class='error'>" + additional_error + "</p>");
					}
				} else {
					enter_additional(settings[1], settings[3], additional_progress);
				}
			} else if (questionnaire === "embodiment") {
				if (embodiment_completed) {
					var embodiment_error = "Participant <strong>" + format_proband_label(settings[1]) + "</strong> already answered the System Usability Scale for task <strong>" + settings[3] + "</strong>.";
					if($(".step_1 .cf > .error").length) {
						$(".step_1 .cf > .error").html(embodiment_error);
					} else {
						$(".step_1 .cf").append("<p class='error'>" + embodiment_error + "</p>");
					}
				} else {
					enter_embodiment(settings[1], settings[3], embodiment_progress);
				}
			} else if (!task_completed) {
				if (progress_entry && progress_entry.step === 3) {
					if (!enter_step3(settings[1], settings[3], progress_entry)) {
						enter_step2(settings[1], settings[3], progress_entry);
					}
				} else {
					enter_step2(settings[1], settings[3], progress_entry);
				}
			} else {
				// if proband already did complete the task throw an error
				var error_paragraph = "Participant <strong>" + format_proband_label(settings[1]) + "</strong> already accomplished task <strong>" + settings[3] + "</strong>.";
				if($(".step_1 .cf > .error").length) {
					$(".step_1 .cf > .error").html(error_paragraph);
				} else {
					$(".step_1 .cf").append("<p class='error'>" + error_paragraph + "</p>");
				}
			}
		}

	});

	/* step 2 */

	$(".step_2 button").live("click", function() {
		// save slider values
		$(".step_2 .slider").each(function(i) {
			data_object["slider_value"][i] = $(this).slider("option", "value");
		});

		data_object["button_clicks"] = new_filled_array(demands.length, 0);
		data_object["pair_choices"] = {};

		// prepare stuff for step 3
		counter = 0;
		random_pairs = pair_combinator(demands);
		pairs_length = random_pairs.length;
		if (!data_object.pair_choices) {
			data_object.pair_choices = {};
		}
		data_object.pair_order = random_pairs;

		set_progress_entry(settings[0], settings[2], {
			proband: settings[0],
			task: settings[2],
			step: 3,
			data_object: data_object,
			random_pairs: random_pairs,
			counter: counter,
			pairs_length: pairs_length,
			started: false
		}, "tlx");
		save_state();

		$(".step_2").hide();
		$(".step_3").show();
		push_history_state({
			view: "step3",
			questionnaire: "tlx",
			proband: settings[0],
			task: settings[2],
			progress: {
				data_object: data_object,
				random_pairs: random_pairs,
				counter: counter,
				pairs_length: pairs_length,
				started: false
			}
		});

		// start button for pairs
		if ( $(".step_3").find("div").length ) {
			$(".step_3 div").html("<button>Start</button>");
		} else {
			$(".step_3").append("<div><button>Start</button></div>");
		}
		// remove/reset "to go" counter
		$(".step_3 .to_go").remove();

	});

	/* additional questions */

	$("#additional_continue").click(function() {
		if (!additional_data) {
			additional_data = ensure_additional_data(null);
		}

		$(".additional_slider").each(function(i) {
			var index = parseInt($(this).attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			additional_data.answers[index] = $(this).slider("option", "value");
		});

		$(".additional_text").each(function(i) {
			var index = parseInt($(this).attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			additional_data.answers[index] = $(this).val();
		});

		$(".additional_choice").each(function(i) {
			var index = parseInt($(this).attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			additional_data.answers[index] = $(this).find("input[type='radio']:checked").val() || "";
		});

		$(".additional_rank").each(function(i) {
			var index = parseInt($(this).attr("data-index"), 10);
			if (isNaN(index)) {
				index = i;
			}
			additional_data.answers[index] = collect_rank_answer($(this));
		});

		var output = build_additional_output(additional_data.answers);

		for (var i = 0; i < final_result.length; i++) {
			if (final_result[i].proband === settings[0]) {
				for (var j = 0; j < final_result[i].tasks.length; j++) {
					if (final_result[i].tasks[j].name === settings[2]) {
						final_result[i].tasks[j].additional = {
							answers: additional_data.answers,
							output: output
						};
						update_export_state();
						clear_progress_entry(settings[0], settings[2], "additional");
						save_state();
						break;
					}
				}
				break;
			}
		}

		$(".step_4 .results").html(output);
		close_edit_panel();
		$("#edit_toggle").prop("disabled", false);
		editing_target = {
			proband: settings[0],
			task: settings[2],
			questionnaire: "additional"
		};

		$(".step_additional").hide();
		$(".step_4").show();
		set_current_questionnaire("additional");
		push_history_state({
			view: "results",
			questionnaire: "additional",
			proband: settings[0],
			task: settings[2]
		});
	});

	$("#embodiment_continue").click(function() {
		if (!embodiment_data) {
			embodiment_data = ensure_embodiment_data(null);
		}

		$(".embodiment_slider").each(function(i) {
			embodiment_data.answers[i] = $(this).slider("option", "value");
		});

		var output = build_embodiment_output(embodiment_data.answers);

		for (var i = 0; i < final_result.length; i++) {
			if (final_result[i].proband === settings[0]) {
				for (var j = 0; j < final_result[i].tasks.length; j++) {
					if (final_result[i].tasks[j].name === settings[2]) {
						final_result[i].tasks[j].embodiment = {
							answers: embodiment_data.answers,
							output: output
						};
						update_export_state();
						clear_progress_entry(settings[0], settings[2], "embodiment");
						save_state();
						break;
					}
				}
				break;
			}
		}

		$(".step_4 .results").html(output);
		close_edit_panel();
		$("#edit_toggle").prop("disabled", false);
		editing_target = {
			proband: settings[0],
			task: settings[2],
			questionnaire: "embodiment"
		};

		$(".step_embodiment").hide();
		$(".step_4").show();
		set_current_questionnaire("embodiment");
		push_history_state({
			view: "results",
			questionnaire: "embodiment",
			proband: settings[0],
			task: settings[2]
		});
	});

	/* step 3 */

	$(".step_3 button").live("click", function() {
		// if a pair button is clicked (start button hasn't got class attribute)
		if( $(this).attr("class") ) {
			var current_pair = random_pairs[counter];
			// count clicks for corresponding demand
			for ( var i = 0; i < demands.length; i++ ) {
				if ( $(this).attr("class") === demands[i][0] ) {
					data_object["button_clicks"][i] += 1;
					break;
				}
			}

			if (current_pair && current_pair.length) {
				var left_id = current_pair[0][0],
					right_id = current_pair[1][0],
					chosen_id = $(this).attr("class"),
					key = pair_key(left_id, right_id);
				if (!data_object.pair_choices) {
					data_object.pair_choices = {};
				}
				data_object.pair_choices[key] = chosen_id;
			}

			pairs_length--;
			counter++;
		}

		// continue as long as there are reaming pairs to be clicked
		if ( pairs_length ) {
			// show the next pair
			$(this)
				.parent()
				.html("<button class='" + random_pairs[counter][0][0] + "'>" + random_pairs[counter][0][1] + "</button> or " + "<button class='" + random_pairs[counter][1][0] + "'>" + random_pairs[counter][1][1] + "</button>");
			// "to go" counter
			if ( !$(".step_3").find(".to_go").length ) {
				$(".step_3").append("<p class='highlight to_go'></p>");
			}
			$(".step_3 .to_go").html("<strong>" + pairs_length + "</strong> to go!");

			set_progress_entry(settings[0], settings[2], {
				proband: settings[0],
				task: settings[2],
				step: 3,
				data_object: data_object,
				random_pairs: random_pairs,
				counter: counter,
				pairs_length: pairs_length,
				started: true
			}, "tlx");
			save_state();
			push_history_state({
				view: "step3",
				questionnaire: "tlx",
				proband: settings[0],
				task: settings[2],
				progress: {
					data_object: data_object,
					random_pairs: random_pairs,
					counter: counter,
					pairs_length: pairs_length,
					started: true
				}
			}, true);
		} else {
			var metrics = build_task_output(data_object["slider_value"], data_object["button_clicks"]);

			$(".step_4 .results").html(metrics.output);
			close_edit_panel();
			$("#edit_toggle").prop("disabled", false);

			// save computed data to array

			// iterate probands
			for (var i = 0; i < final_result.length; i++) {
				// if proband already saved
				if (final_result[i].proband === settings[0]) {
					// iterate tasks
					for (var j = 0; j < final_result[i].tasks.length; j++) {
						if (final_result[i].tasks[j].name === settings[2]) {
							final_result[i].tasks[j].data = data_object;
							final_result[i].tasks[j].tlx = metrics.tlx;
							final_result[i].tasks[j].output = metrics.output;
							update_export_state();
							clear_progress_entry(settings[0], settings[2], "tlx");
							save_state();
							break;
						}
					}
					break;
				}
			}

			// table output for overview page
			tableoutput = build_table_output();

			$(".step_3").hide();
			$(".step_4").show();
			editing_target = {
				proband: settings[0],
				task: settings[2],
				questionnaire: "tlx"
			};
			push_history_state({
				view: "results",
				questionnaire: "tlx",
				proband: settings[0],
				task: settings[2]
			});

		}

	}); // step 3 button

	/* step 4 */
	$("#step_4_back").click(function() {
		$(".info").remove();
		$(".step_0 p").remove();

		render_overview();
		close_edit_panel();

		$(".step_4").hide();
		$(".step_0").show();
		set_page_title("overview");
		push_history_state({
			view: "overview",
			questionnaire: current_questionnaire
		});

	}); // step 4 button

	$(window).on("popstate", function(event) {
		navigate_to_state(event.originalEvent.state);
	});

	push_history_state({
		view: "overview",
		questionnaire: current_questionnaire
	}, true);

});
