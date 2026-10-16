import React from "react";
type Props = {
  disabled?: boolean;
  onChange: (...args: Array<any>) => any;
  onKeyUp: (...args: Array<any>) => any;
  onSubmit: (...args: Array<any>) => any;
  placeholder?: string;
  type?: string;
  value: string;
};

const SearchInput = ({
  disabled,
  onChange,
  onKeyUp,
  onSubmit,
  placeholder = "Cari dengan kata kunci",
  type = "text",
  value = "",
}: Props) => {
  return (
    <div className="search-input__component">
      <label className="search-input__label" htmlFor="top-navigation__search">
        Cari dengan kata kunci
      </label>
      <input
        className="search-input"
        disabled={disabled}
        id="top-navigation__search"
        name="top-navigation__search"
        onChange={onChange}
        onKeyUp={onKeyUp}
        placeholder={placeholder}
        type={type}
        value={value}
      />
      <span
        className="search-icon"
        role="button"
        tabIndex={0}
        onClick={onSubmit}
        onKeyDown={(e: React.KeyboardEvent) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onSubmit();
          }
        }}
      ></span>
    </div>
  );
};

export default SearchInput;
