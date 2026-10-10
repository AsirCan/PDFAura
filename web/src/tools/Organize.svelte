<script lang="ts">
  // Faz 3 of #25 moves this tool here; until then --web shows only its hint.
  import { t } from "../lib/i18n.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";
</script>

<ToolLayout hint={t("hint_split")}>
  <p class="hint">{t("page_meta_organize_body")}</p>
</ToolLayout>
