import os
import sys

from crewai import Agent, Crew, LLM, Process, Task
from crewai_tools import SerperDevTool
from dotenv import load_dotenv

load_dotenv()


def _require_api_keys():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    serper_api_key = os.getenv("SERPER_API_KEY")

    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
    if not serper_api_key:
        raise RuntimeError("SERPER_API_KEY environment variable is not set.")

    return gemini_api_key


def _result_markdown(result):
    """Pull the final markdown string out of a CrewAI result."""
    return getattr(result, "raw", None) or str(result)


def build_research_crew():
    gemini_api_key = _require_api_keys()

    search_tool = SerperDevTool()
    gemini_llm = LLM(
        model="gemini/gemini-2.5-flash",
        api_key=gemini_api_key,
    )

    researcher = Agent(
        role="Study Research Specialist",
        goal="Gather accurate, clear, student-friendly facts, definitions, and examples about {topic}",
        backstory=(
            "You are a patient teacher and researcher. You find trustworthy information "
            "and explain complex ideas in simple terms a student can understand and remember."
        ),
        tools=[search_tool],
        llm=gemini_llm,
        verbose=True,
    )

    writer = Agent(
        role="Study Notes Author",
        goal="Turn research into clear, exam-ready study notes on {topic}",
        backstory=(
            "You are a brilliant teacher who writes the study notes students love: "
            "well-organized, easy to skim, with bold key terms, simple examples, and quick "
            "revision questions. You never overwhelm; you make topics feel learnable."
        ),
        llm=gemini_llm,
        verbose=True,
    )

    research_task = Task(
        description=(
            "Research the topic for a student: {topic}. "
            "Search the web for accurate, up-to-date information. Collect the core concepts, "
            "clear definitions of key terms, simple real-world examples, common points of "
            "confusion, and a few source URLs a student could read to learn more."
        ),
        expected_output=(
            "A bulleted list of key concepts, term definitions, examples, common mistakes, "
            "and source URLs."
        ),
        agent=researcher,
    )

    write_task = Task(
        description=(
            "Using the research, write clear study notes in markdown about {topic}. "
            "A student should be able to revise from these notes before an exam. "
            "Use exactly these sections:\n"
            "# {topic}\n"
            "## Overview  (2-3 sentence plain-English summary)\n"
            "## Key Concepts  (each as **Term** — short definition)\n"
            "## Detailed Notes  (subheadings per subtopic, short bullet points)\n"
            "## Examples  (1-3 simple, concrete examples)\n"
            "## Quick Revision  (5 short question-and-answer pairs)\n"
            "## References  (the source URLs)\n"
            "Keep language simple. Bold important terms. Prefer short bullets over long paragraphs."
        ),
        expected_output="Clean, well-structured markdown study notes a student can revise from.",
        agent=writer,
    )

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
        process=Process.sequential,
    )


LEVEL_GUIDANCE = {
    "easy": (
        "Rewrite for a beginner or younger student. Use very simple, everyday language and "
        "short sentences. Explain any technical term in plain words, use friendly analogies, "
        "and keep it short and encouraging. Avoid jargon."
    ),
    "medium": (
        "Rewrite as balanced study notes for a typical student revising for an exam: clear, "
        "well-organized, with the key details but not overwhelming."
    ),
    "high": (
        "Rewrite as in-depth, advanced notes. Add technical depth, precise terminology, deeper "
        "explanations, nuances, edge cases, and how concepts connect. Be thorough and detailed."
    ),
}


def relevel_notes(topic, source_markdown, level):
    """Rewrite existing notes at a difficulty level. No web search — cheap, single LLM pass."""
    gemini_api_key = _require_api_keys()

    gemini_llm = LLM(model="gemini/gemini-2.5-flash", api_key=gemini_api_key)
    guidance = LEVEL_GUIDANCE.get(level, LEVEL_GUIDANCE["medium"])

    adapter = Agent(
        role="Study Notes Adapter",
        goal="Rewrite existing study notes about {topic} at the requested difficulty level",
        backstory=(
            "You are a versatile teacher who can explain the same topic to a curious child or "
            "a graduate student. You keep the facts accurate while changing the depth and wording "
            "to match the reader."
        ),
        llm=gemini_llm,
        verbose=True,
    )

    adapt_task = Task(
        description=(
            "You are given existing study notes about {topic}.\n\n"
            "EXISTING NOTES:\n{source_notes}\n\n"
            "Rewrite these notes. {level_guidance}\n"
            "Keep the same markdown section structure (# title, Overview, Key Concepts, "
            "Detailed Notes, Examples, Quick Revision, References). Keep the same source URLs in "
            "the References section unchanged. Bold important terms."
        ),
        expected_output="Rewritten markdown study notes at the requested level.",
        agent=adapter,
    )

    crew = Crew(agents=[adapter], tasks=[adapt_task], process=Process.sequential)
    result = crew.kickoff(
        inputs={"topic": topic, "source_notes": source_markdown, "level_guidance": guidance}
    )
    return _result_markdown(result)


def run_research(topic):
    crew = build_research_crew()
    result = crew.kickoff(inputs={"topic": topic})
    return _result_markdown(result)


if __name__ == "__main__":
    print("Generating study notes with the Gemini study crew...")
    try:
        result = run_research("Photosynthesis")
    except RuntimeError as exc:
        sys.exit(f"Error: {exc}")
    print("\n--- Process Complete! ---")
    print(result)
