<script lang="ts">
  // Faz 3 of #25 moves this tool here; until then --web shows only its hint.
  import { t } from "../lib/i18n.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";
</script>

<ToolLayout hint={t("hint_advanced")}>
  <p class="hint">{t("page_meta_advanced_body")}</p>
</ToolLayout>
