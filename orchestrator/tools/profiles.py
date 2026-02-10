"""Profile management tools — list and create translation profiles."""

import os
import json
import glob as globmod


def list_profiles(profiles_dir: str = "examples/profiles") -> str:
    """List available translation profiles with their key settings.

    Args:
        profiles_dir: Directory containing profile JSON files.

    Returns:
        JSON string with profile summaries.
    """
    if not os.path.isdir(profiles_dir):
        return json.dumps({"error": f"Profiles directory not found: {profiles_dir}"})

    profiles = []
    for path in sorted(globmod.glob(os.path.join(profiles_dir, "*.json"))):
        basename = os.path.basename(path)
        if basename.startswith("_"):
            continue

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            profiles.append({
                "file": basename,
                "path": path,
                "name": data.get("name", basename),
                "description": data.get("description", ""),
                "source_language": data.get("source_language", "English"),
                "protected_nouns_count": len(data.get("protected_nouns", [])),
                "glossary_seed_count": len([k for k in data.get("glossary_seed", {}) if k != "_comment"]),
                "temperature": data.get("temperature", {}).get("translate", 0.3),
                "min_review_chars": data.get("min_review_chars", 300),
            })
        except Exception as e:
            profiles.append({"file": basename, "error": str(e)})

    return json.dumps({"profiles": profiles, "total": len(profiles)}, ensure_ascii=False, indent=2)


def create_profile(
    name: str,
    output_path: str,
    description: str = "",
    source_language: str = "English",
    style_instructions: str = "",
    protected_nouns: str = "",
    glossary_seed: str = "",
    temp_translate: float = 0.3,
    temp_review: float = 0.4,
    temp_refine: float = 0.2,
    min_review_chars: int = 300,
    context_update_interval: int = 15,
    glossary_update_interval: int = 20,
) -> str:
    """Create a new translation profile JSON file.

    Args:
        name: Profile name (e.g. "Gothic Horror")
        output_path: Where to save the profile JSON
        description: Description of the profile's purpose
        source_language: Source language (default: English)
        style_instructions: Multi-line style instructions for the translator
        protected_nouns: Comma-separated list of nouns to never translate
        glossary_seed: JSON string of seed glossary {"source": "target", ...}
        temp_translate: Temperature for translation pass (0.0-1.0)
        temp_review: Temperature for review pass (0.0-1.0)
        temp_refine: Temperature for refinement pass (0.0-1.0)
        min_review_chars: Minimum chars before triggering review
        context_update_interval: Update context every N chunks
        glossary_update_interval: Update glossary every N chunks

    Returns:
        JSON string with result status.
    """
    # Parse protected nouns
    nouns_list = [n.strip() for n in protected_nouns.split(",") if n.strip()] if protected_nouns else []

    # Parse glossary seed
    seed = {}
    if glossary_seed:
        try:
            seed = json.loads(glossary_seed)
            if not isinstance(seed, dict):
                seed = {}
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid glossary_seed JSON: {glossary_seed}"})

    profile = {
        "name": name,
        "description": description,
        "source_language": source_language,
        "style_instructions": style_instructions,
        "protected_nouns": nouns_list,
        "glossary_seed": seed,
        "temperature": {
            "translate": temp_translate,
            "review": temp_review,
            "refine": temp_refine,
        },
        "min_review_chars": min_review_chars,
        "context_update_interval": context_update_interval,
        "glossary_update_interval": glossary_update_interval,
    }

    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    return json.dumps({
        "status": "created",
        "path": output_path,
        "name": name,
        "protected_nouns": len(nouns_list),
        "glossary_seed_terms": len(seed),
    })
