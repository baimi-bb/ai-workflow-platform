export type FormFeedbackState = {
  ok: boolean;
  message: string | null;
};

export const DEFAULT_FORM_FEEDBACK_STATE: FormFeedbackState = {
  ok: false,
  message: null,
};
