"""UI strings for the languages beyond Turkish and English.

Each module holds one STRINGS dict keyed like lang_manager's English one.
Keys a module leaves out fall back to English. Two groups are left out on
purpose:

- the file-name suffixes (suffix_*, security_suffix_*), so output names stay
  plain ASCII instead of picking up other scripts or direction marks;
- batch_rename_default, because batch.py only understands the Turkish and
  English naming tokens. batch_rename_hint is translated but keeps the
  English tokens for the same reason.
"""
