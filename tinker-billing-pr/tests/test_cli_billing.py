"""Tests for tinker billing CLI commands."""

import json

import click
import pytest
from click.testing import CliRunner

from tinker.cli.commands.billing import EstimateOutput, RatesOutput, _PRICING, _lookup, cli


class TestLookup:
    def test_known_model(self) -> None:
        rates = _lookup("Qwen/Qwen3.5-9B")
        assert rates == (0.44, 1.33, 1.33)

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(click.BadParameter, match="Unknown model"):
            _lookup("nonexistent/model")

    def test_all_pricing_entries_are_positive(self) -> None:
        for model, (p, s, t) in _PRICING.items():
            assert p > 0 and s > 0 and t > 0, f"Non-positive rate for {model}"


class TestEstimateOutput:
    def _make(self, prefill=0, sample=0, train=0, model="Qwen/Qwen3.5-9B"):
        rates = _lookup(model)
        return EstimateOutput(model, prefill, sample, train, rates)

    def test_prefill_only(self) -> None:
        out = self._make(prefill=1_000_000)
        data = out.to_dict()
        assert data["prefill_cost"] == pytest.approx(0.44)
        assert data["sample_cost"] == 0.0
        assert data["train_cost"] == 0.0
        assert data["total_cost"] == pytest.approx(0.44)

    def test_all_operations(self) -> None:
        out = self._make(prefill=1_000_000, sample=1_000_000, train=1_000_000)
        data = out.to_dict()
        assert data["total_cost"] == pytest.approx(0.44 + 1.33 + 1.33)

    def test_fractional_millions(self) -> None:
        out = self._make(prefill=500_000)  # half a million tokens
        data = out.to_dict()
        assert data["prefill_cost"] == pytest.approx(0.22)

    def test_to_dict_has_all_keys(self) -> None:
        out = self._make(prefill=100)
        data = out.to_dict()
        assert set(data) == {
            "model", "prefill_tokens", "sample_tokens", "train_tokens",
            "prefill_cost", "sample_cost", "train_cost", "total_cost",
        }

    def test_table_rows_omit_zero_operations(self) -> None:
        out = self._make(prefill=1000)
        rows = out.get_table_rows()
        operations = [r[0] for r in rows]
        assert "Prefill" in operations
        assert "Sample" not in operations
        assert "Train" not in operations
        assert rows[-1][0] == "Total"

    def test_table_rows_include_all_when_nonzero(self) -> None:
        out = self._make(prefill=1000, sample=1000, train=1000)
        rows = out.get_table_rows()
        operations = [r[0] for r in rows]
        assert operations == ["Prefill", "Sample", "Train", "Total"]


class TestRatesOutput:
    def test_to_dict_contains_all_models(self) -> None:
        data = RatesOutput(_PRICING).to_dict()
        assert set(data.keys()) == set(_PRICING.keys())

    def test_each_entry_has_three_rates(self) -> None:
        data = RatesOutput(_PRICING).to_dict()
        for model, rates in data.items():
            assert set(rates) == {"prefill", "sample", "train"}, model

    def test_table_has_four_columns(self) -> None:
        out = RatesOutput(_PRICING)
        assert len(out.get_table_columns()) == 4

    def test_table_row_count_matches_pricing(self) -> None:
        out = RatesOutput(_PRICING)
        assert len(out.get_table_rows()) == len(_PRICING)


class TestEstimateCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def _invoke(self, args):
        from tinker.cli.context import CLIContext
        return self.runner.invoke(cli, args, obj=CLIContext(format="table"), catch_exceptions=False)

    def test_estimate_table_output(self) -> None:
        result = self._invoke([
            "estimate", "--model", "Qwen/Qwen3.5-9B",
            "--prefill-tokens", "1000000",
        ])
        assert result.exit_code == 0
        assert "Prefill" in result.output
        assert "$0.44" in result.output

    def test_estimate_json_output(self) -> None:
        from tinker.cli.context import CLIContext
        result = self.runner.invoke(
            cli,
            ["estimate", "--model", "Qwen/Qwen3.5-9B", "--prefill-tokens", "1000000"],
            obj=CLIContext(format="json"),
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["prefill_cost"] == pytest.approx(0.44)

    def test_estimate_requires_at_least_one_token_count(self) -> None:
        result = self.runner.invoke(
            cli, ["estimate", "--model", "Qwen/Qwen3.5-9B"],
            obj=__import__("tinker.cli.context", fromlist=["CLIContext"]).CLIContext(format="table"),
        )
        assert result.exit_code != 0
        assert "at least one" in result.output.lower() or "at least one" in (result.exception and str(result.exception) or "").lower()

    def test_estimate_unknown_model_fails(self) -> None:
        from tinker.cli.context import CLIContext
        result = self.runner.invoke(
            cli, ["estimate", "--model", "fake/model", "--prefill-tokens", "1000"],
            obj=CLIContext(format="table"),
        )
        assert result.exit_code != 0

    def test_rates_lists_all_models(self) -> None:
        from tinker.cli.context import CLIContext
        result = self.runner.invoke(cli, ["rates"], obj=CLIContext(format="table"), catch_exceptions=False)
        assert result.exit_code == 0
        assert "Qwen/Qwen3.5-9B" in result.output

    def test_rates_json_output(self) -> None:
        from tinker.cli.context import CLIContext
        result = self.runner.invoke(cli, ["rates"], obj=CLIContext(format="json"), catch_exceptions=False)
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "Qwen/Qwen3.5-9B" in data
        assert data["Qwen/Qwen3.5-9B"]["prefill"] == 0.44
