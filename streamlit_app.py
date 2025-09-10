import streamlit as st
from logic import extract_commit_memory, generate_story, summarize_commits

# -------------------------------
# Streamlit App
# -------------------------------
st.set_page_config(page_title="Repo Historian", layout="wide")

st.title("📜 Repo Journey Explorer")
st.write(
    "Analyze your Git repository’s commits and generate a narrated story."
)

# Input: Repo Path
repo_path = st.text_input("Enter the path to your Git repository:", value=".")
max_commits = st.slider("How many commits to analyze?", 5, 100, 20)
max_recent = st.slider("How many recent commits to display in detail?", 3, 20, 10)

# Commit type emoji map
color_map = {
    "Setup": "🟢",
    "Feature": "🔵",
    "Fix": "🔴",
    "Refactor": "🟡",
    "Test": "🟣",
    "Other": "⚪",
}

# File purpose color map
file_color_map = {
    "Python source code": "lightblue",
    "Documentation": "lightgreen",
    "Configuration file": "orange",
    "Configuration/data file": "yellow",
    "Git ignore rules": "grey",
    "Other": "white",
}

if st.button("🚀 Generate Story"):
    with st.spinner("🔍 Extracting commit metadata..."):
        memory = extract_commit_memory(repo_path, max_commits=max_commits)

    if not memory:
        st.error("❌ No commits found in this repository.")
    else:
        st.subheader("📊 Commit Metadata (Chronological)")

        # Separate recent and older commits for compact display
        recent_memory = memory[-max_recent:]
        older_memory = memory[:-max_recent]

        # Scrollable container for commits
        with st.container():
            st.markdown(
                "<div style='max-height:500px; overflow-y:auto;'>", unsafe_allow_html=True
            )

            # Older commits summarized
            summarized_older = summarize_commits(older_memory)
            for summary in summarized_older:
                st.markdown(f"⚪ {summary}")

            # Recent commits fully detailed
            for commit in recent_memory:
                # Cap large line numbers for display
                insertions = commit.get('insertions', 0)
                deletions = commit.get('deletions', 0)
                display_insertions = f">1000+" if insertions > 1000 else str(insertions)
                display_deletions = f">1000-" if deletions > 1000 else str(deletions)
                size_info = f"{display_insertions}+ / {display_deletions}-"

                # Truncate long commit messages
                message = commit.get('message', '')
                truncated_msg = message if len(message) <= 80 else message[:77] + "..."

                # Expander for each commit
                with st.expander(f"{color_map.get(commit['type'], '⚪')} Commit {commit['commit_number']}: {truncated_msg}", expanded=False):
                    st.markdown(f"""
                        <i>Date:</i> {commit['date']} &nbsp;&nbsp;|&nbsp;&nbsp; 
                        <i>Author:</i> <code>{commit['author']}</code> &nbsp;&nbsp;|&nbsp;&nbsp; 
                        <i>Type:</i> {commit['type']}<br>
                        <i>Files Changed:</i> {commit.get('files_changed_count', 0)} &nbsp;&nbsp;|&nbsp;&nbsp;
                        <i>Lines:</i> {size_info}
                    """, unsafe_allow_html=True)

                    # File-level details
                    key_files = commit.get('key_files', [])
                    if key_files:
                        st.markdown("**Changed Files:**")
                        for f in key_files:
                            color = file_color_map.get(f['purpose'], "white")
                            st.markdown(f"<span style='background-color:{color};padding:2px 6px;border-radius:3px;'>{f['name']} ({f['purpose']}) +{f['insertions']}/-{f['deletions']}</span>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        # Story generation (preset temperature)
        st.subheader("📖 Repo Journey Story")
        temperature = 0.7
        with st.spinner("✨ Generating repo story with LLM..."):
            story = generate_story(memory, temperature=temperature, max_recent=max_recent)
        st.success("✅ Story generated successfully!")
        st.markdown(story)
