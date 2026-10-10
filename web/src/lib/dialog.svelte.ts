// In-window questions ("replace this file?"): one at a time, answered with
// the keyboard or the mouse. ConfirmDialog.svelte draws the open one.
export interface Question {
  title: string;
  body: string;
  confirm: string;
  cancel: string;
  danger?: boolean;
}

class Dialogs {
  open = $state<Question | null>(null);
  private resolve: ((answer: boolean) => void) | null = null;

  ask(question: Question): Promise<boolean> {
    this.answer(false);
    this.open = question;
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }

  answer(yes: boolean) {
    const resolve = this.resolve;
    this.resolve = null;
    this.open = null;
    resolve?.(yes);
  }
}

export const dialogs = new Dialogs();
