<script lang="ts">
  // A Segoe Fluent Icons glyph, by meaning (lib/generated/icons.ts).
  import { Icons, type IconName } from "../lib/generated/icons";

  // flip: arrows that point "forward" mirror in right-to-left languages.
  let { name, size = 16, flip = false }: { name: IconName; size?: number; flip?: boolean } = $props();
</script>

<i class="icon" class:flip aria-hidden="true" style:font-size="{size}px">{Icons[name]}</i>

<style>
  :global([dir="rtl"]) .flip {
    transform: scaleX(-1);
  }
</style>
