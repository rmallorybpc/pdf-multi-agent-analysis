from pdf_multi_agent_analysis.agents import AnalystAgent, ExtractorAgent, LegalRiskAgent, ReviewerAgent, SynthesizerAgent


def test_agents_produce_non_empty_output() -> None:
    sample = "# Heading\nSome body text with TODO action item."

    outputs = [
        ExtractorAgent().run(sample).content,
        ReviewerAgent().run(sample).content,
        AnalystAgent().run(sample).content,
        LegalRiskAgent().run(sample).content,
        SynthesizerAgent().run(sample).content,
    ]

    assert all(bool(o.strip()) for o in outputs)


def test_synthesizer_preview_is_coherent_for_long_input() -> None:
    sentence = "This sentence is intentionally long enough to exercise preview generation logic. "
    sample = sentence * 20

    output = SynthesizerAgent().run(sample).content

    assert output.startswith("Summary preview: ")
    assert len(output) > 60
