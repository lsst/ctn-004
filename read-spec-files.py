import re
import requests
from astropy.io import fits
from typing import NamedTuple

class Card(NamedTuple):
    source: str
    group: str
    header: str
    type: str
    spec: str
    description: str
    example: str = ""
    notes: str = ""


def split(s, maxIndex):
    result = []
    index = 0
    iter = re.finditer(r'(".+?"|[\S]+)\s*', s)
    for i in iter:
        result.append(i.group(1))
        index += 1
        if index >= maxIndex:
            result.append(s[i.end() :])
            break
    return result


def read_spec_file(url, source) -> tuple[dict[str, str], dict[str, Card]]:
    response = requests.get(url)
    if response.status_code == 200:
        groups = {}
        result = {}
        for line_bytes in response.iter_lines():
            # Decode the bytes to a string (assuming UTF-8 encoding)
            line = line_bytes.decode("utf-8")
            if line.startswith("#"):
                continue
            if line.strip() == "":
                continue
            if line.startswith("BLANK"):
                spec = split(line, 2)
                if len(spec) == 3:
                    groups[spec[1]] = spec[2]
            else:
                spec = split(line, 3)
                if len(spec) < 4:
                    spec += [" "]
                key = spec[0]
                if ":" in key:
                    group, key = key.split(":", 1)
                else:
                    group = "None"
                key = key.replace("!", "")
                result[key] = Card(*[source, group, key] + spec[1:])
        return (groups, result)
    else:
        raise FileNotFoundError(url)


def combine_spec_files(baseURL, files):
    results = {}
    groups = {}
    for file in files:
        url = baseURL + file + ".spec"
        group, result = read_spec_file(url, file)
        groups.update(group)
        results.update(result)
    return (groups, results)


def get_example_values_from_fits_header(fits_file, result):
    with fits.open(fits_file) as hdul:
        primaryHDU = hdul[0]

    for key, value in result.items():
        if key in primaryHDU.header:
            demoValue = primaryHDU.header[key]
            value += [str(demoValue)]
        else:
            value += ["MISSING"]


def writeAsCSV(file, specs):
    with open(file, "w") as f:
        f.write("Source\tGroup\tHeader\tType\tSpec\tDescription\tExample\tNotes")
        f.write("\n")
        for spec in specs.values():
            f.write("\t".join(spec))
            f.write("\n")

def escape_latex(text: str) -> str:
    """Escape LaTeX special characters in a string."""
    replacements = {
        "\\": "\\textbackslash{}",  # Must be first to avoid double escaping.
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def get_header_version(specs: dict[str, Card]) -> str:
    """Extract the header version from the specifications."""
    for card in specs.values():
        if card.header == "HEADVER":
            return card.spec
    return "Unknown"


def write_as_latex(
    file: str,
    groups: dict[str, str],
    specs: dict[str, Card],
    header_version: str = "Unknown",
):
    """Write the specifications to a LaTeX table format.

    Write each group out as a separate table and only include
    the header name, type, and description.
    """
    # Group headers by their group name
    grouped_specs = {}

    # Seed the order from the supplied groups.
    grouped_specs["None"] = []
    for group_name in groups:
        grouped_specs[group_name] = []

    for card in specs.values():
        group = card.group
        grouped_specs[group].append(card)
        if card.header == "HEADVER":
            header_version = card.spec

    with open(file, "w") as f:
        print(f"Header Version: {header_version}", file=f)

        for group_name, cards in grouped_specs.items():
            if not cards:
                continue
            description = groups.get(group_name)
            if not description:
                if group_name == "None":
                    description = "No Group Assigned"
                else:
                    description = group_name + " Group"
            # Remove the ---- from start and end of the description.
            description = re.sub("--+", "", description)
            description = escape_latex(description.strip())

            print(rf"""
\subsubsection{{{description}}}
""", file=f)
            print(r"""
\begin{tabular}{l l l l l}
\hline
Header & Type & Description \\
\hline""", file=f)

            for spec in cards:
                f.write(
                    f"{escape_latex(spec.header.replace(".", " "))} & "
                    f"{escape_latex(spec.type)} & "
                    f"{escape_latex(spec.description)} \\\\\n"
                )
            print(r"""\hline
\end{tabular}
""", file=f)


baseURL = "https://lsst-camera-dev.slac.stanford.edu/RestFileServer/rest/version/download/misc/spec-files-combined/"
lsstcam_primary_files = [
    "primary-groups",
    "merged-primary",
    "lsstcam-primary",
    "header-service-primary",
    "filter",
]

groups, result = combine_spec_files(baseURL, lsstcam_primary_files)

header_version = get_header_version(result)

write_as_latex("lsstcam-primary.tex", groups, result, header_version)

auxtel_primary_files = [
    "primary-groups",
    "merged-primary",
    "ats-primary",
    "header-service-primary",
    "ats-header-service-primary",
]

at_groups, result = combine_spec_files(baseURL, auxtel_primary_files)
groups.update(at_groups)

write_as_latex("auxtel-primary.tex", groups, result, header_version)

# Amplifier header.
amplifier_files = [
    "extended",
]
amplifier_groups, result = combine_spec_files(baseURL, amplifier_files)
groups.update(amplifier_groups)

print("\n\n-----\n\n")
write_as_latex("amplifier.tex", groups, result, header_version)
