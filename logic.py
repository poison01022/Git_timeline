import os
import tempfile
from datetime import datetime
from git import Repo
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -------------------------------
# Ensure OpenAI client
# -------------------------------
def _ensure_openai():
    """Ensure OpenAI client is available and API key is set."""
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment.")
    return OpenAI(api_key=key)

# -------------------------------
# Get or clone repo
# -------------------------------
def get_repo(repo_path):
    if repo_path.startswith("http"):
        temp_dir = os.path.join(tempfile.gettempdir(), "repo_cache")
        os.makedirs(temp_dir, exist_ok=True)
        local_path = os.path.join(temp_dir, os.path.basename(repo_path).replace(".git", ""))
        if not os.path.exists(local_path):
            Repo.clone_from(repo_path, local_path)
        return Repo(local_path)
    else:
        return Repo(repo_path)

# -------------------------------
# Classify commit importance
# -------------------------------
def classify_importance(message: str) -> str:
    msg = message.lower()
    if any(k in msg for k in ["init", "setup", "initial"]):
        return "Setup"
    elif any(k in msg for k in ["add", "feature", "implement"]):
        return "Feature"
    elif any(k in msg for k in ["fix", "bug", "issue"]):
        return "Fix"
    elif any(k in msg for k in ["refactor", "cleanup"]):
        return "Refactor"
    elif "test" in msg:
        return "Test"
    else:
        return "Other"

# -------------------------------
# Infer file purpose
# -------------------------------
def infer_file_purpose(filename):
    fname = filename.lower()
    if fname.endswith(".py"):
        return "Python source code"
    elif fname.endswith(".md"):
        return "Documentation"
    elif fname.endswith(".gitignore"):
        return "Git ignore rules"
    elif fname.endswith(".json"):
        return "Configuration/data file"
    elif fname.endswith((".yml", ".yaml")):
        return "Configuration file"
    else:
        return "Other"

# -------------------------------
# Extract commit memory
# -------------------------------
def extract_commit_memory(repo_path: str, max_commits: int = 50, top_files: int = 5):
    """
    Extract structured commit memory including key files, purposes, and line changes.
    """
    repo = get_repo(repo_path)
    commits = list(repo.iter_commits("HEAD", max_count=max_commits))
    commits.reverse()  # oldest first

    memory = []
    for idx, commit in enumerate(commits, 1):
        stats = commit.stats.total
        num_files = len(commit.stats.files)

        # Top files with insertions/deletions
        important_files = []
        for f, s in list(commit.stats.files.items())[:top_files]:
            important_files.append({
                "name": f,
                "purpose": infer_file_purpose(f),
                "insertions": s.get("insertions", 0),
                "deletions": s.get("deletions", 0)
            })

        memory.append({
            "commit_number": idx,
            "author": commit.author.name if commit.author else "Unknown",
            "date": datetime.utcfromtimestamp(commit.committed_date).strftime("%Y-%m-%d"),
            "message": commit.message.strip(),
            "type": classify_importance(commit.message),
            "summary": commit.message.strip().splitlines()[0],
            "key_files": important_files,
            "insertions": stats.get("insertions", 0),
            "deletions": stats.get("deletions", 0),
            "files_changed_count": num_files,
        })
    return memory

# -------------------------------
# Summarize older commits into compact form
# -------------------------------
def summarize_commits(memory, max_tokens_per_commit=200):
    """
    Create a concise summary of each commit for LLM input.
    Reduces token usage while retaining essential info.
    """
    summarized = []
    for c in memory:
        files_info = ", ".join([f"{f['name']} ({f['purpose']}): +{f['insertions']}/-{f['deletions']}"
                                for f in c['key_files']])
        text = (
            f"Commit {c['commit_number']} by {c['author']} on {c['date']} "
            f"[{c['type']}]: {c['summary']}. "
            f"Files changed ({c['files_changed_count']}): {files_info}. "
            f"Insertions: {c['insertions']}, Deletions: {c['deletions']}."
        )
        # Optional: truncate extremely long commit text to keep tokens in check
        if len(text) > max_tokens_per_commit:
            text = text[:max_tokens_per_commit] + " [...]"
        summarized.append(text)
    return summarized

# -------------------------------
# Generate narrated story incrementally
# -------------------------------
def generate_story(memory, temperature=0.3, max_recent=10):
    """
    Generate a narrated repo journey efficiently.
    Summarizes older commits, keeps recent commits detailed.
    """
    client = _ensure_openai()
    sys_prompt = (
        "You are a narrator. Write the repository's journey one detailed paragraph per commit. "
        "Start each paragraph with 'Commit X:'. For each commit, mention key files changed, "
        "their purpose/type, insertions/deletions, and overall impact. "
        "Keep it concise, engaging, and informative. Do NOT include commit hashes."
    )

    # Split memory into older and recent commits
    recent_memory = memory[-max_recent:]
    older_memory = memory[:-max_recent]

    # Summarize older commits
    summarized_older = summarize_commits(older_memory)

    # Build memory text for LLM
    user_text = "Repository commit memory:\n"
    for c in summarized_older:
        user_text += c + "\n"
    for c in recent_memory:
        files_info = ", ".join([f"{f['name']} ({f['purpose']}): +{f['insertions']}/-{f['deletions']}"
                                for f in c['key_files']])
        user_text += (
            f"Commit {c['commit_number']} by {c['author']} on {c['date']} "
            f"[{c['type']}]: {c['summary']}. "
            f"Files changed ({c['files_changed_count']}): {files_info}. "
            f"Insertions: {c['insertions']}, Deletions: {c['deletions']}.\n"
        )

    user_text += "\nWrite a narrated story with one paragraph per commit."

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=temperature,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_text},
        ],
    )

    return resp.choices[0].message.content.strip()

# -------------------------------
# Test
# -------------------------------
if __name__ == "__main__":
    repo_path = "."  # current repo or remote URL
    memory = extract_commit_memory(repo_path, max_commits=50)

    print("==== Structured Commit Memory ====")
    for m in memory:
        print(m)

    print("\n==== Narrated Story ====")
    story = generate_story(memory)
    print(story)
