<script lang="ts">
  // A labelled path box with its Browse / Save as button.
  let { label, value = $bindable(""), button, onbrowse, oninput, placeholder = "", id }:
    { label: string; value?: string; button: string; onbrowse: () => void; oninput?: (value: string) => void;
      placeholder?: string; id: string } = $props();
</script>

<div class="file-field">
  <label class="field-label" for={id}>{label}</label>
  <div class="row">
    <input
      {id}
      class="input grow"
      type="text"
      dir="auto"
      spellcheck="false"
      {placeholder}
      bind:value
      oninput={() => oninput?.(value)}
    />
    <button class="btn btn-secondary" type="button" onclick={onbrowse}>{button}</button>
  </div>
</div>

<style>
  .file-field + :global(.file-field) {
    margin-top: 16px;
  }
</style>
