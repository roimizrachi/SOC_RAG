#!/usr/bin/env python3
import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS = REPO_ROOT / "data" / "event_metadata_records_82303.json"

STOPWORDS = {
    "a",
    "an",
    "and",
    "appear",
    "appears",
    "are",
    "as",
    "at",
    "be",
    "by",
    "did",
    "do",
    "does",
    "event",
    "events",
    "for",
    "found",
    "from",
    "give",
    "in",
    "is",
    "it",
    "me",
    "of",
    "offense",
    "on",
    "present",
    "show",
    "tell",
    "the",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "exe",
    "dll",
    "sys",
    "bat",
    "cmd",
    "ps1",
    "vbs",
    "js",
    "msi",
    "com",
    "scr",
    "dat",
    "txt",
    "log",
}

DEFAULT_DISPLAY_FIELDS = [
    "cisco.detection",
    "normalized.name",
    "computer.hostname",
    "qradar.sourceip",
    "qradar.destinationip",
    "cisco.severity",
    "actions.name",
    "observables.file.name",
    "observables.registry.key",
    "observables.registry.value",
    "registry_set.data_txt",
]

IP_ADDRESS_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOTTED_NUMERIC_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")
HASH_RE = re.compile(r"\b[a-fA-F0-9]{32,64}\b")
UUID_RE = re.compile(
    r"\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b"
)
FILE_NAME_RE = re.compile(
    r"\b[A-Za-z0-9_$~+%-][A-Za-z0-9_$~+%.-]*\."
    r"(?:exe|dll|sys|bat|cmd|ps1|vbs|js|msi|com|scr|dat|txt|log)\b",
    re.IGNORECASE,
)
HOSTNAME_RE = re.compile(
    r"\b(?=[A-Za-z0-9.-]*[A-Za-z])(?=[A-Za-z0-9.-]*\.)"
    r"[A-Za-z0-9][A-Za-z0-9.-]{2,}[A-Za-z0-9]\b"
)
HOSTNAME_LIKE_RE = re.compile(
    r"\b(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)(?=[A-Za-z0-9-]*-)"
    r"[A-Za-z0-9][A-Za-z0-9-]{2,}[A-Za-z0-9]\b"
)
REGISTRY_PATH_RE = re.compile(
    r"(?i)(?:\\machine|hkey_local_machine|hklm|hkey_current_user|hkcu|"
    r"hkey_classes_root|hkcr|hkey_users|hku)(?:[\\/][A-Za-z0-9_. -]+)+"
)

STRICT_IDENTIFIER_CATEGORIES = {"ip", "dotted_numeric", "hash", "uuid", "registry_path"}
FUZZY_IDENTIFIER_CATEGORIES = {"file_name", "hostname"}


def load_event_metadata_records(path=DEFAULT_RECORDS):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "events" not in data or not isinstance(data["events"], list):
        raise ValueError("Event metadata records file must contain an 'events' list")
    return data


def flatten_values(value):
    if value is None:
        return []
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(flatten_values(item))
        return values
    if isinstance(value, dict):
        values = []
        for key in sorted(value):
            values.append(key)
            values.extend(flatten_values(value[key]))
        return values
    if value == "":
        return []
    return [value]


def field_name_text(field_name):
    spaced = re.sub(r"[._-]+", " ", field_name)
    expanded = re.sub(r"\b(source|destination|event|logsource|severity|connector)(ip|id)\b", r"\1 \2", spaced)
    return [field_name, spaced, expanded]


def build_metadata_text(fields):
    parts = []
    for field_name in sorted(fields):
        values = flatten_values(fields[field_name])
        if not values:
            continue
        parts.extend(field_name_text(field_name))
        parts.extend(str(value) for value in values)
    return " ".join(parts)


def build_metadata_value_text(fields):
    parts = []
    for field_name in sorted(fields):
        values = flatten_values(fields[field_name])
        if values:
            parts.extend(str(value) for value in values)
    return " ".join(parts)


def normalize(text):
    text = str(text).lower()
    text = text.replace("_", " ").replace(".", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_identifier(identifier):
    normalized = str(identifier).strip().strip(".,;:()[]{}\"'").lower()
    normalized = normalized.replace("/", "\\") if normalized.startswith(("\\", "hkey_", "hklm", "hkcu", "hkcr", "hku")) else normalized
    return re.sub(r"\\+", r"\\", normalized)


def is_file_name(identifier):
    return FILE_NAME_RE.fullmatch(identifier) is not None


def is_numeric_dotted(identifier):
    return bool(re.fullmatch(r"\d+(?:\.\d+)+", identifier))


def add_identifier(matches, seen, category, match):
    identifier = normalize_identifier(match.group(0))
    if not identifier or (category, identifier) in seen:
        return
    seen.add((category, identifier))
    matches.append((match.start(), category, identifier))


def extract_identifier_matches(text):
    text = str(text)
    matches = []
    seen = set()
    hostname_spans = []

    for match in IP_ADDRESS_RE.finditer(text):
        add_identifier(matches, seen, "ip", match)
    for match in DOTTED_NUMERIC_RE.finditer(text):
        if not IP_ADDRESS_RE.fullmatch(match.group(0)):
            add_identifier(matches, seen, "dotted_numeric", match)
    for match in HASH_RE.finditer(text):
        add_identifier(matches, seen, "hash", match)
    for match in UUID_RE.finditer(text):
        add_identifier(matches, seen, "uuid", match)
    for match in FILE_NAME_RE.finditer(text):
        add_identifier(matches, seen, "file_name", match)
    for match in REGISTRY_PATH_RE.finditer(text):
        add_identifier(matches, seen, "registry_path", match)

    non_hostname_identifiers = {identifier for _, _, identifier in matches}
    for match in HOSTNAME_RE.finditer(text):
        identifier = normalize_identifier(match.group(0))
        if identifier in non_hostname_identifiers:
            continue
        if is_file_name(identifier) or is_numeric_dotted(identifier):
            continue
        hostname_spans.append(match.span())
        add_identifier(matches, seen, "hostname", match)

    for match in HOSTNAME_LIKE_RE.finditer(text):
        start, end = match.span()
        if any(start >= hostname_start and end <= hostname_end for hostname_start, hostname_end in hostname_spans):
            continue
        identifier = normalize_identifier(match.group(0))
        if is_file_name(identifier) or is_numeric_dotted(identifier):
            continue
        add_identifier(matches, seen, "hostname", match)

    matches.sort(key=lambda item: (item[0], item[1], item[2]))
    return [{"category": category, "value": identifier} for _, category, identifier in matches]


def extract_identifiers(text):
    identifiers = {}
    for match in extract_identifier_matches(text):
        identifiers.setdefault(match["category"], [])
        if match["value"] not in identifiers[match["category"]]:
            identifiers[match["category"]].append(match["value"])
    return identifiers


def identifier_values(identifier_map, categories=None):
    selected = []
    for category, values in identifier_map.items():
        if categories is not None and category not in categories:
            continue
        selected.extend(values)
    return selected


def word_tokens(text):
    return [token for token in normalize(text).split() if token and token not in STOPWORDS]


def tokenize(text, identifier_source=None):
    tokens = word_tokens(text)
    source = text if identifier_source is None else identifier_source
    for identifier in identifier_values(extract_identifiers(source)):
        tokens.append(identifier)
    return tokens


def unique_preserving_order(items):
    seen = set()
    unique_items = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique_items.append(item)
    return unique_items


def selected_fields(fields, display_fields=DEFAULT_DISPLAY_FIELDS):
    return {
        field_name: fields[field_name]
        for field_name in display_fields
        if field_name in fields and flatten_values(fields[field_name])
    }


def build_search_documents(records):
    documents = []
    for fallback_index, event in enumerate(records["events"]):
        identity = event.get("event_identity", {})
        fields = event.get("fields", {})
        text = build_metadata_text(fields)
        value_text = build_metadata_value_text(fields)
        identifiers = extract_identifiers(value_text)
        tokens = tokenize(text, identifier_source=value_text)
        event_index = identity.get("event_index", fallback_index)
        documents.append(
            {
                "event_index": event_index,
                "event_id": identity.get("event_id"),
                "fields": fields,
                "text": text,
                "tokens": tokens,
                "term_counts": Counter(tokens),
                "identifiers": identifiers,
                "identifier_tokens": set(identifier_values(identifiers)),
                "strict_identifier_tokens": set(identifier_values(identifiers, STRICT_IDENTIFIER_CATEGORIES)),
                "fuzzy_identifier_tokens": set(identifier_values(identifiers, FUZZY_IDENTIFIER_CATEGORIES)),
            }
        )
    return documents


def document_frequencies(documents):
    frequencies = Counter()
    for document in documents:
        frequencies.update(set(document["tokens"]))
    return frequencies


def inverse_document_frequency(term, document_count, frequencies):
    frequency = frequencies.get(term, 0)
    return math.log(1 + (document_count - frequency + 0.5) / (frequency + 0.5))


def bm25_score(query_tokens, document, document_count, frequencies, average_length, k1=1.5, b=0.75):
    score = 0.0
    document_length = len(document["tokens"])
    if document_length == 0:
        return score

    for token in query_tokens:
        term_frequency = document["term_counts"].get(token, 0)
        if term_frequency == 0:
            continue

        idf = inverse_document_frequency(token, document_count, frequencies)
        denominator = term_frequency + k1 * (1 - b + b * document_length / max(average_length, 1))
        score += idf * (term_frequency * (k1 + 1) / denominator)

    return score


def levenshtein_distance(left, right):
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def fuzzy_threshold(token):
    if len(token) <= 4:
        return 1
    if len(token) <= 8:
        return 2
    return 3


def fuzzy_match_score(query_token, candidate):
    if query_token == candidate:
        return 1.0, "exact"
    if len(query_token) < 4 or len(candidate) < 4:
        return 0.0, None

    shorter = min(len(query_token), len(candidate))
    longer = max(len(query_token), len(candidate))
    if shorter >= 4 and (query_token.startswith(candidate) or candidate.startswith(query_token)):
        return shorter / longer, "partial"

    if abs(len(query_token) - len(candidate)) > fuzzy_threshold(query_token):
        return 0.0, None

    distance = levenshtein_distance(query_token, candidate)
    if distance > fuzzy_threshold(query_token):
        return 0.0, None

    ratio = 1 - (distance / longer)
    if min(len(query_token), len(candidate)) <= 4:
        return 0.0, None
    if ratio < 0.72:
        return 0.0, None
    return ratio, "fuzzy"


def query_analysis(query):
    identifiers = extract_identifiers(query)
    identifier_tokens = set(identifier_values(identifiers))
    return {
        "tokens": unique_preserving_order(tokenize(query)),
        "identifiers": identifiers,
        "identifier_tokens": identifier_tokens,
        "strict_identifier_tokens": set(identifier_values(identifiers, STRICT_IDENTIFIER_CATEGORIES)),
        "fuzzy_identifier_tokens": set(identifier_values(identifiers, FUZZY_IDENTIFIER_CATEGORIES)),
        "query_type": "identifier_like" if identifier_tokens else "free_text",
    }


def hostname_identifier_matches(analysis, document):
    matches = []
    query_hostnames = analysis["identifiers"].get("hostname", [])
    document_hostnames = document["identifiers"].get("hostname", [])
    for query_hostname in query_hostnames:
        for document_hostname in document_hostnames:
            if (
                query_hostname == document_hostname
                or document_hostname.startswith(f"{query_hostname}.")
                or query_hostname in document_hostname
            ):
                matches.append(document_hostname)
    return sorted(set(matches))


def hostname_segments(hostname):
    return [segment for segment in re.split(r"[.-]+", hostname) if segment]


def hostname_text_segments(hostname):
    return [segment for segment in hostname_segments(hostname) if not segment.isdigit()]


def hostname_numeric_segments(hostname):
    return [segment for segment in hostname_segments(hostname) if segment.isdigit()]


def bounded_hostname_fuzzy_score(query_hostname, document_hostname):
    query_numbers = hostname_numeric_segments(query_hostname)
    document_numbers = hostname_numeric_segments(document_hostname)
    if query_numbers and not all(number in document_numbers for number in query_numbers):
        return 0.0

    query_text = hostname_text_segments(query_hostname)
    document_text = hostname_text_segments(document_hostname)
    if not query_text or not document_text:
        return 0.0

    matched_scores = []
    for query_segment in query_text:
        best_score = 0.0
        for document_segment in document_text:
            score, match_type = fuzzy_match_score(query_segment, document_segment)
            if match_type == "exact":
                score = 1.0
            if score > best_score:
                best_score = score
        if best_score == 0.0:
            return 0.0
        matched_scores.append(best_score)

    average_score = sum(matched_scores) / len(matched_scores)
    if average_score < 0.82:
        return 0.0
    return average_score


def bounded_hostname_fuzzy_matches(analysis, document):
    matches = []
    query_hostnames = analysis["identifiers"].get("hostname", [])
    document_hostnames = document["identifiers"].get("hostname", [])
    for query_hostname in query_hostnames:
        for document_hostname in document_hostnames:
            if document_hostname in hostname_identifier_matches(analysis, document):
                continue
            score = bounded_hostname_fuzzy_score(query_hostname, document_hostname)
            if score > 0:
                matches.append({"query": query_hostname, "matched": document_hostname, "score": round(score, 4)})
    matches.sort(key=lambda item: (-item["score"], item["matched"]))
    return matches


def exact_identifier_matches(analysis, document):
    matches = analysis["identifier_tokens"] & document["identifier_tokens"]
    matches = matches | set(hostname_identifier_matches(analysis, document))
    return sorted(matches)


def fuzzy_identifier_matches(analysis, document):
    matches = set(exact_identifier_matches(analysis, document))
    matches.update(match["matched"] for match in bounded_hostname_fuzzy_matches(analysis, document))
    return sorted(matches)


def strict_identifier_matches(analysis, document):
    return sorted(analysis["strict_identifier_tokens"] & document["strict_identifier_tokens"])


def identifier_query_can_match_bm25(analysis, document):
    if not analysis["identifier_tokens"]:
        return True
    return bool(exact_identifier_matches(analysis, document))


def strict_identifier_query_can_fuzzy_match(analysis, document):
    if not analysis["strict_identifier_tokens"]:
        if analysis["identifiers"].get("hostname"):
            return bool(hostname_identifier_matches(analysis, document) or bounded_hostname_fuzzy_matches(analysis, document))
        return True
    return bool(strict_identifier_matches(analysis, document))


def is_weak_identifier_fragment(token, analysis):
    return bool(analysis["identifier_tokens"]) and token.isdigit() and len(token) <= 3


def exact_matched_terms(query_tokens, document, analysis):
    document_terms = set(document["tokens"])
    matches = []
    for token in query_tokens:
        if is_weak_identifier_fragment(token, analysis):
            continue
        if token in document_terms:
            matches.append(
                {
                    "query_term": token,
                    "matched_term": token,
                    "match_type": "exact",
                    "score": 1.0,
                }
            )
    return matches


def best_fuzzy_match(query_token, document, document_count, frequencies):
    best = None
    for candidate in set(document["tokens"]):
        score, match_type = fuzzy_match_score(query_token, candidate)
        if not match_type or match_type == "exact":
            continue

        idf = inverse_document_frequency(candidate, document_count, frequencies)
        weighted_score = idf * score * 0.45
        candidate_match = {
            "query_term": query_token,
            "matched_term": candidate,
            "match_type": match_type,
            "score": round(score, 4),
            "weighted_score": weighted_score,
        }
        if best is None:
            best = candidate_match
            continue
        if (weighted_score, candidate) > (best["weighted_score"], best["matched_term"]):
            best = candidate_match
    return best


def fuzzy_matches(query_tokens, document, document_count, frequencies, analysis):
    matches = []
    for token in query_tokens:
        if is_weak_identifier_fragment(token, analysis):
            continue
        fuzzy_match = best_fuzzy_match(token, document, document_count, frequencies)
        if fuzzy_match:
            matches.append(fuzzy_match)
    return matches


def result_row(document, score, matched_terms, method, matched_identifiers=None):
    return {
        "event_index": document["event_index"],
        "event_id": document["event_id"],
        "score": round(score, 4),
        "matched_terms": matched_terms,
        "matched_identifiers": matched_identifiers or [],
        "fields": selected_fields(document["fields"]),
        "method": method,
    }


def rank_results(results, limit):
    results.sort(key=lambda result: (-result["score"], result["event_index"]))
    return results[:limit]


def empty_result(query, method):
    identifiers = extract_identifiers(query)
    return {
        "query": query,
        "method": method,
        "query_type": "identifier_like" if identifier_values(identifiers) else "free_text",
        "query_identifiers": identifiers,
        "results": [],
    }


def search_metadata_text_bm25(query, records_path=DEFAULT_RECORDS, limit=10, min_score=0.0):
    query = query.strip()
    method = "bm25_metadata_text"
    if not query:
        return empty_result(query, method)

    records = load_event_metadata_records(records_path)
    documents = build_search_documents(records)
    analysis = query_analysis(query)
    query_tokens = analysis["tokens"]
    if not query_tokens or not documents:
        return empty_result(query, method)

    document_count = len(documents)
    frequencies = document_frequencies(documents)
    average_length = sum(len(document["tokens"]) for document in documents) / document_count
    results = []

    for document in documents:
        if not identifier_query_can_match_bm25(analysis, document):
            continue

        score = bm25_score(query_tokens, document, document_count, frequencies, average_length)
        if score <= min_score:
            continue

        matched_terms = exact_matched_terms(query_tokens, document, analysis)
        if not matched_terms:
            continue

        results.append(
            result_row(
                document,
                score,
                matched_terms,
                method,
                matched_identifiers=exact_identifier_matches(analysis, document),
            )
        )

    return {
        "query": query,
        "method": method,
        "query_type": analysis["query_type"],
        "query_identifiers": analysis["identifiers"],
        "results": rank_results(results, limit),
    }


def search_metadata_text_fuzzy(query, records_path=DEFAULT_RECORDS, limit=10, min_score=0.0):
    query = query.strip()
    method = "fuzzy_metadata_text"
    if not query:
        return empty_result(query, method)

    records = load_event_metadata_records(records_path)
    documents = build_search_documents(records)
    analysis = query_analysis(query)
    query_tokens = analysis["tokens"]
    if not query_tokens or not documents:
        return empty_result(query, method)

    document_count = len(documents)
    frequencies = document_frequencies(documents)
    results = []

    for document in documents:
        if not strict_identifier_query_can_fuzzy_match(analysis, document):
            continue

        matches = fuzzy_matches(query_tokens, document, document_count, frequencies, analysis)
        fuzzy_only_matches = [match for match in matches if match["match_type"] in {"fuzzy", "partial"}]
        score = sum(match["weighted_score"] for match in fuzzy_only_matches)
        if score <= min_score or not fuzzy_only_matches:
            continue

        matched_terms = []
        for match in fuzzy_only_matches:
            clean_match = dict(match)
            clean_match.pop("weighted_score", None)
            matched_terms.append(clean_match)

        results.append(
            result_row(
                document,
                score,
                matched_terms,
                method,
                matched_identifiers=fuzzy_identifier_matches(analysis, document),
            )
        )

    return {
        "query": query,
        "method": method,
        "query_type": analysis["query_type"],
        "query_identifiers": analysis["identifiers"],
        "results": rank_results(results, limit),
    }


def search_metadata_text(query, records_path=DEFAULT_RECORDS, limit=10, min_score=0.0, mode="bm25"):
    if mode == "bm25":
        return search_metadata_text_bm25(query, records_path=records_path, limit=limit, min_score=min_score)
    if mode == "fuzzy":
        return search_metadata_text_fuzzy(query, records_path=records_path, limit=limit, min_score=min_score)
    raise ValueError("mode must be 'bm25' or 'fuzzy'")


def main():
    parser = argparse.ArgumentParser(description="Search Event Metadata Records with deterministic metadata text search.")
    parser.add_argument("--query", required=True, help="Metadata text search query")
    parser.add_argument("--records", default=str(DEFAULT_RECORDS), help="Path to event metadata records JSON")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of ranked events to return")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum score")
    parser.add_argument("--mode", choices=["bm25", "fuzzy"], default="bm25", help="Metadata text search mode")
    args = parser.parse_args()

    result = search_metadata_text(
        args.query,
        records_path=args.records,
        limit=args.limit,
        min_score=args.min_score,
        mode=args.mode,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
