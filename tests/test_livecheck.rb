# frozen_string_literal: true

require "minitest/autorun"
require_relative "../scripts/ci/livecheck"

class TapLivecheckTest < Minitest::Test
  QUALIFIED = "mbianchidev/tap/example-app"

  def output(current: "1.2.3", latest: "1.2.3", outdated: false, newer: false)
    JSON.generate([{
      "cask"    => "example-app",
      "version" => {
        "current" => current, "latest" => latest, "outdated" => outdated, "newer_than_upstream" => newer
      },
    }])
  end

  def test_current_release_passes_and_pending_release_only_warns
    assert_nil TapLivecheck.evaluate(output, QUALIFIED)
    warning = TapLivecheck.evaluate(output(latest: "1.2.4", outdated: true), QUALIFIED)
    assert_match "1.2.3 is behind upstream 1.2.4", warning
  end

  def test_broken_livecheck_or_definition_ahead_of_upstream_fails
    error = JSON.generate([{ "cask" => "example-app", "status" => "error", "messages" => ["Mock failure"] }])
    current = JSON.parse(output).first
    [
      error, "[]", "{}", "not json",
      output(latest: ""), output(outdated: nil), JSON.generate([current, current])
    ].each do |text|
      assert_raises(RuntimeError) { TapLivecheck.evaluate(text, QUALIFIED) }
    end
    assert_raises(RuntimeError) { TapLivecheck.evaluate(output(current: "1.2.4", newer: true), QUALIFIED) }
  end
end
