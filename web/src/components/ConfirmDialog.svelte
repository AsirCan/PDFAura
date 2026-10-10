<script lang="ts">
  // The open question from lib/dialog.svelte.ts, as a modal <dialog>:
  // Esc answers no, the confirm button has the focus.
  import { dialogs } from "../lib/dialog.svelte";

  let dialog: HTMLDialogElement | undefined = $state();

  $effect(() => {
    if (!dialog) return;
    if (dialogs.open && !dialog.open) dialog.showModal?.();
    else if (!dialogs.open && dialog.open) dialog.close();
  });
</script>

<dialog
  bind:this={dialog}
  class="card"
  aria-labelledby="confirm-title"
  oncancel={(event) => {
    event.preventDefault();
    dialogs.answer(false);
  }}
>
  {#if dialogs.open}
    <h2 id="confirm-title" class="title">{dialogs.open.title}</h2>
    <p class="body muted selectable">{dialogs.open.body}</p>
    <div class="row actions">
      <button class="btn btn-secondary" onclick={() => dialogs.answer(false)}>{dialogs.open.cancel}</button>
      <!-- svelte-ignore a11y_autofocus -->
      <button class="btn {dialogs.open.danger ? 'btn-danger' : 'btn-primary'}" autofocus
              onclick={() => dialogs.answer(true)}>{dialogs.open.confirm}</button>
    </div>
  {/if}
</dialog>

<style>
  dialog {
    width: min(460px, calc(100vw - 48px));
    padding: 22px 24px 20px;
    color: var(--text);
    box-shadow: 0 12px 40px color-mix(in srgb, var(--stage) 30%, transparent);
  }
  dialog::backdrop {
    background: color-mix(in srgb, var(--stage) 45%, transparent);
  }
  h2 {
    margin: 0;
  }
  p {
    margin: 10px 0 0;
    white-space: pre-line;
    overflow-wrap: anywhere;
  }
  .actions {
    justify-content: flex-end;
    margin-top: 20px;
  }
</style>
