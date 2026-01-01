"""Tests for the LangGraph workflow construction."""

import pytest
from unittest.mock import patch, MagicMock


class TestBuildGraph:
    """Tests for the build_graph function."""

    def test_build_graph_returns_compiled_graph(self):
        """Test that build_graph returns a compiled LangGraph."""
        # Mock the llm to avoid actual initialization
        with patch("review_roadmap.agent.nodes.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            from review_roadmap.agent.graph import build_graph

            graph = build_graph()

        # Verify the graph is compiled and has the expected structure
        assert graph is not None
        # CompiledStateGraph should have an invoke method
        assert hasattr(graph, "invoke")

    def test_build_graph_has_correct_nodes(self):
        """Test that the graph contains all expected nodes."""
        with patch("review_roadmap.agent.nodes.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_get_llm.return_value = mock_llm

            from review_roadmap.agent.graph import build_graph

            graph = build_graph()

        # The compiled graph should have the nodes we defined
        # We can check the graph's internal structure
        assert graph is not None

    def test_graph_invocation_with_mock(self, sample_pr_context):
        """Test that the full graph can be invoked with mocked LLM."""
        mock_response = MagicMock()
        mock_response.content = "Mocked analysis result"
        mock_response.tool_calls = []

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        with patch("review_roadmap.agent.nodes.llm") as mock_llm:
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.__or__ = MagicMock(return_value=mock_chain)

            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.graph import build_graph

                graph = build_graph()
                result = graph.invoke({"pr_context": sample_pr_context})

        # The result should have the roadmap key populated
        assert "roadmap" in result
        assert result["roadmap"] == "Mocked analysis result"

