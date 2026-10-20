import React from "react";
import DatePicker, { registerLocale } from "react-datepicker";
import { TextInput } from "hds-react";
import format from "date-fns/format";
import parse from "date-fns/parse";
import idLocale from "date-fns/locale/id";
import { isValidDate } from "@/util/date";

registerLocale("id", idLocale);

/** Format nilai tanggal pencarian sewa (juga dipakai di URL pencarian). */
export const SEARCH_DATE_FORMAT = "dd.MM.yyyy";

/** Baca "d.M.yyyy" / "dd.MM.yyyy"; nilai yang tidak valid menjadi null. */
export const parseSearchDate = (value?: string | null): Date | null => {
  if (!value) return null;
  const date = parse(value, "d.M.yyyy", new Date());
  return isValidDate(date) ? date : null;
};

export const formatSearchDate = (date: Date | null): string =>
  date ? format(date, SEARCH_DATE_FORMAT) : "";

type Props = {
  id: string;
  label: string;
  value: string;
  onBlur?: (...args: Array<any>) => any;
  onChange: (value: string) => void;
  onFocus?: (...args: Array<any>) => any;
  className?: string;
  style?: React.CSSProperties;
};

/**
 * Kolom tanggal pencarian dengan kalender berbahasa Indonesia. DateInput HDS
 * hanya mengenal bahasa fi/sv/en sehingga nama bulan dan harinya berbahasa
 * Inggris.
 */
const SearchDateInput = ({
  id,
  label,
  value,
  onBlur,
  onChange,
  onFocus,
  className,
  style,
}: Props): JSX.Element => (
  <DatePicker
    id={id}
    locale="id"
    dateFormat={SEARCH_DATE_FORMAT}
    selected={parseSearchDate(value)}
    onChange={(date: Date | null) => onChange(formatSearchDate(date))}
    onBlur={onBlur}
    onFocus={onFocus}
    showYearDropdown
    dropdownMode="select"
    placeholderText="hh.bb.tttt"
    wrapperClassName="lease-search__date-input"
    popperClassName="lease-search__date-popper"
    previousMonthButtonLabel="Bulan sebelumnya"
    nextMonthButtonLabel="Bulan berikutnya"
    customInput={
      <TextInput id={id} label={label} className={className} style={style} />
    }
  />
);

export default SearchDateInput;
