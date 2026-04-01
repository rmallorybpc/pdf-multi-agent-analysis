from pdf_multi_agent_analysis.agents import AnalystAgent, ExtractorAgent, ReviewerAgent, SynthesizerAgent


def test_agents_produce_non_empty_output() -> None:
    sample = "# Heading\nSome body text with TODO action item."

    outputs = [
        ExtractorAgent().run(sample).content,
        ReviewerAgent().run(sample).content,
        AnalystAgent().run(sample).content,
        SynthesizerAgent().run(sample).content,
    ]

    assert all(bool(o.strip()) for o in outputs)
