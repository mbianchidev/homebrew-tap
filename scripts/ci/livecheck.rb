# frozen_string_literal: true

require "json"

# Separates broken livecheck metadata from upstream releases the hourly updater has not landed yet.
module TapLivecheck
  # Returns a warning for a pending upstream release, nil when current, and raises for unusable results.
  def self.evaluate(output, qualified)
    results = JSON.parse(output)
    result = results.first if results.is_a?(Array) && results.length == 1
    version = result["version"] if result.is_a?(Hash)
    raise "livecheck could not resolve #{qualified}: #{output.strip}" if
      !version.is_a?(Hash) || !version["current"].is_a?(String) ||
      !version["latest"].is_a?(String) || version["latest"].empty? ||
      [version["outdated"], version["newer_than_upstream"]].any? { |flag| ![true, false].include?(flag) }
    raise "#{qualified} #{version["current"]} is newer than upstream #{version["latest"]}." if
      version["newer_than_upstream"]
    return unless version["outdated"]

    "#{qualified} #{version["current"]} is behind upstream #{version["latest"]}; " \
      "the hourly updater publishes verified releases."
  rescue JSON::ParserError
    raise "livecheck returned invalid JSON for #{qualified}: #{output.strip}"
  end
end
