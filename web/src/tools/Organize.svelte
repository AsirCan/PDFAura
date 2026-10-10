<script lang="ts">
  // Split, Merge and Edit pages behind one sidebar entry, switched above
  // them. Each keeps its state.
  import { onMount } from "svelte";
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import Segmented from "../components/Segmented.svelte";
  import EditPages from "./EditPages.svelte";
  import Merge from "./Merge.svelte";
  import Split from "./Split.svelte";

  type Group = "split" | "merge" | "edit";
  let group = $state<Group>("split");
  let tools: Partial<Record<Group, { drop: (files: import("../lib/types").FileInfo[]) => void }>> = $state({});

  onMount(() => app.acceptDrops("organize", (files) => tools[group]?.drop(files)));
</script>

<div class="organize">
  <Segmented canvas label={t("txt_edit")} bind:value={group} options={[
    { value: "split", label: t("txt_split") },
    { value: "merge", label: t("txt_merge") },
    { value: "edit", label: t("txt_edit") },
  ]} />
  <div class="tool" hidden={group !== "split"}><Split bind:this={tools.split} /></div>
  <div class="tool" hidden={group !== "merge"}><Merge bind:this={tools.merge} /></div>
  <div class="tool" hidden={group !== "edit"}><EditPages bind:this={tools.edit} /></div>
</div>

<style>
  .organize {
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }
  .organize > :global(.segmented) {
    align-self: flex-start;
  }
  .tool {
    flex: 1 1 auto;
    min-height: 0;
  }
  .tool[hidden] {
    display: none;
  }
</style>
