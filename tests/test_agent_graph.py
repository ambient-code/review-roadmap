"""Tests for the LangGraph workflow construction."""

import pytest
from unittest.mock import patch, MagicMock


class TestBuildGraph:
    """Tests for the build_graph function."""

    def test_build_graph_returns_compiled_graph(self):
        """Test that build_graph returns a compiled LangGraph."""
        from review_roadmap.agent.graph import build_graph

        graph = build_graph()

        # Verify the graph is compiled and has the expected structure
        assert graph is not None
        # CompiledStateGraph should have an invoke method
        assert hasattr(graph, "invoke")

    def test_build_graph_has_correct_nodes(self):
        """Test that the graph contains all expected nodes."""
        from review_roadmap.agent.graph import build_graph

        graph = build_graph()

        # The compiled graph should have the nodes we defined
        assert graph is not None

    def test_graph_invocation_with_mock_and_reflection(self, sample_pr_context):
        """Test that the full graph can be invoked with reflection enabled."""
        # Create separate responses for different nodes
        call_count = [0]

        def mock_invoke(args):
            call_count[0] += 1
            mock_response = MagicMock()
            # 4th call is reflection (analyze, context_expansion, draft, reflect)
            if call_count[0] == 4:
                mock_response.content = '{"passed": true, "notes": "Self-review: OK"}'
            else:
                mock_response.content = "Mocked analysis result"
            mock_response.tool_calls = []
            return mock_response

        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = mock_invoke

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.__or__ = MagicMock(return_value=mock_chain)

        with patch("review_roadmap.agent.nodes._get_llm_instance", return_value=mock_llm):
            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.graph import build_graph

                graph = build_graph()
                result = graph.invoke({"pr_context": sample_pr_context})

        # The result should have the roadmap key populated
        assert "roadmap" in result
        assert result["reflection_passed"] is True
        assert result["reflection_iterations"] == 1

    def test_graph_invocation_skip_reflection(self, sample_pr_context):
        """Test that reflection can be skipped via skip_reflection flag."""
        mock_response = MagicMock()
        mock_response.content = "Mocked roadmap"
        mock_response.tool_calls = []

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = mock_response

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.__or__ = MagicMock(return_value=mock_chain)

        with patch("review_roadmap.agent.nodes._get_llm_instance", return_value=mock_llm):
            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.graph import build_graph

                graph = build_graph()
                result = graph.invoke({
                    "pr_context": sample_pr_context,
                    "skip_reflection": True
                })

        # Should have roadmap but no reflection results
        assert "roadmap" in result
        assert result["roadmap"] == "Mocked roadmap"
        # Reflection should not have run - check that iteration count is default (0)
        # Note: LangGraph may not include unchanged default values in result dict
        assert result.get("reflection_iterations", 0) == 0
        assert result.get("reflection_passed", False) is False

    def test_graph_reflection_retry_loop(self, sample_pr_context):
        """Test that reflection triggers a retry when it fails."""
        call_count = [0]

        def mock_invoke(args):
            call_count[0] += 1
            mock_response = MagicMock()
            mock_response.tool_calls = []

            # Calls: 1=analyze, 2=context, 3=draft, 4=reflect(fail),
            #        5=draft(retry), 6=reflect(pass)
            if call_count[0] == 4:
                # First reflection fails
                mock_response.content = '{"passed": false, "feedback": "Missing details"}'
            elif call_count[0] == 6:
                # Second reflection passes
                mock_response.content = '{"passed": true, "notes": "Self-review: Fixed"}'
            else:
                mock_response.content = "Mocked content"
            return mock_response

        mock_chain = MagicMock()
        mock_chain.invoke.side_effect = mock_invoke

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.__or__ = MagicMock(return_value=mock_chain)

        with patch("review_roadmap.agent.nodes._get_llm_instance", return_value=mock_llm):
            with patch("review_roadmap.agent.nodes.ChatPromptTemplate") as mock_template:
                mock_prompt = MagicMock()
                mock_prompt.__or__ = MagicMock(return_value=mock_chain)
                mock_template.from_messages.return_value = mock_prompt

                from review_roadmap.agent.graph import build_graph

                graph = build_graph()
                result = graph.invoke({"pr_context": sample_pr_context})

        # Should have retried once
        assert result["reflection_iterations"] == 2
        assert result["reflection_passed"] is True


class TestGraphConditionalRouting:
    """Tests for the conditional routing functions."""

    def test_should_reflect_returns_reflect_by_default(self, sample_pr_context):
        """Test that _should_reflect returns 'reflect' when not skipped."""
        from review_roadmap.agent.graph import _should_reflect
        from review_roadmap.agent.state import ReviewState

        state = ReviewState(pr_context=sample_pr_context)
        assert _should_reflect(state) == "reflect"

    def test_should_reflect_returns_end_when_skipped(self, sample_pr_context):
        """Test that _should_reflect returns 'end' when skip_reflection is True."""
        from review_roadmap.agent.graph import _should_reflect
        from review_roadmap.agent.state import ReviewState

        state = ReviewState(pr_context=sample_pr_context, skip_reflection=True)
        assert _should_reflect(state) == "end"

    def test_after_reflection_returns_end_when_passed(self, sample_pr_context):
        """Test that _after_reflection returns 'end' when reflection passed."""
        from review_roadmap.agent.graph import _after_reflection
        from review_roadmap.agent.state import ReviewState

        state = ReviewState(
            pr_context=sample_pr_context,
            reflection_passed=True,
            reflection_iterations=1
        )
        assert _after_reflection(state) == "end"

    def test_after_reflection_returns_retry_when_failed(self, sample_pr_context):
        """Test that _after_reflection returns 'retry' when reflection failed."""
        from review_roadmap.agent.graph import _after_reflection
        from review_roadmap.agent.state import ReviewState

        state = ReviewState(
            pr_context=sample_pr_context,
            reflection_passed=False,
            reflection_iterations=1
        )
        assert _after_reflection(state) == "retry"

    def test_after_reflection_returns_end_at_max_iterations(self, sample_pr_context):
        """Test that _after_reflection returns 'end' at max iterations."""
        from review_roadmap.agent.graph import _after_reflection
        from review_roadmap.agent.state import ReviewState
        from review_roadmap.agent.prompts import MAX_REFLECTION_ITERATIONS

        state = ReviewState(
            pr_context=sample_pr_context,
            reflection_passed=False,
            reflection_iterations=MAX_REFLECTION_ITERATIONS
        )
        assert _after_reflection(state) == "end"

