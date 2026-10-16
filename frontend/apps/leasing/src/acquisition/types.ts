export type Choice = { value: string; label: string };
export type ChoiceMap = Record<string, Array<Choice>>;

/** Metadata kolom dari DRF OPTIONS. */
export type FieldMeta = {
  type:
    | "string"
    | "choice"
    | "boolean"
    | "date"
    | "datetime"
    | "decimal"
    | "integer"
    | "email"
    | "url"
    | "field"
    | "file"
    | string;
  required: boolean;
  read_only: boolean;
  label: string;
  max_length?: number;
  min_value?: number;
  max_value?: number;
  choices?: Array<{ value: string | number; display_name: string }>;
};

export type Option = { value: string | number; label: string };

export type Deadline = {
  project_id: number;
  project_identifier: string;
  project_name: string;
  kind: string;
  title: string;
  due_date: string;
  reference: string;
  parcel_id: number | null;
  parcel_number: string | null;
  workdays_left: number;
  state: "upcoming" | "due_soon" | "overdue";
};

export type Project = Record<string, any> & {
  id: number;
  identifier: string;
  name: string;
};
