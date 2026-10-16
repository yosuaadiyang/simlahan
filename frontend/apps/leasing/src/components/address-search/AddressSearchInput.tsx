import React, { Component } from "react";
import classNames from "classnames";
import { debounce } from "lodash-es";
import Loader from "@/components/loader/Loader";
import LoaderWrapper from "@/components/loader/LoaderWrapper";
import { stringifyQuery } from "@/api/createUrl";
import { KeyCodes } from "@/enums";
const MINIMUM_SEARCH_STRING = 3;
const DEBOUNCE_TIME_MILLISECONDS = 500;
const NOMINATIM_URL =
  import.meta.env.VITE_GEOCODER_URL || "https://nominatim.openstreetmap.org";

/** Hasil geocoding Nominatim (OpenStreetMap). */
type Address = {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
  address: {
    road?: string;
    house_number?: string;
    village?: string;
    suburb?: string;
    city?: string;
    town?: string;
    county?: string;
    state?: string;
    postcode?: string;
    country?: string;
    country_code?: string;
  };
};

const getStreetAddress = (address: Address): string => {
  const { road, house_number } = address.address || {};
  if (road) return house_number ? `${road} No. ${house_number}` : road;
  return address.display_name.split(",")[0];
};

const getCity = (address: Address): string => {
  const parts = address.address || {};
  return parts.city || parts.town || parts.county || parts.state || "";
};

type Props = {
  addressDetailsCallBack?: (...args: Array<any>) => any;
  id?: string;
  name?: string;
  onBlur?: (...args: Array<any>) => any;
  onChange?: (...args: Array<any>) => any;
  selected?: string | null | undefined;
  autoComplete?: any;
  disabled?: boolean;
};
type State = {
  addresses: Array<Address>;
  filteredAddresses: Array<Address>;
  focusedValue: Record<string, any> | null | undefined;
  hasFocus: boolean;
  isLoading: boolean;
  menuOpen: boolean;
  selectedAddress: Address | null | undefined;
  value: string | null | undefined;
};

class AddressSearchInput extends Component<Props, State> {
  rootRef: React.RefObject<HTMLDivElement>;
  input: any;
  menuList: any;
  state = {
    addresses: [],
    filteredAddresses: [],
    focusedValue: null,
    hasFocus: false,
    isLoading: false,
    menuOpen: false,
    selectedAddress: null,
    value: this.props.selected || "",
  };
  constructor(props: Props) {
    super(props);
    this.rootRef = React.createRef();
  }

  setInputRef = (el: any) => {
    this.input = el;
  };
  refMenuListRef = (el: any) => {
    this.menuList = el;
  };

  componentDidMount() {
    window.addEventListener("click", this.onDocumentClick);
    window.addEventListener("keydown", this.onKeyDown);
  }

  componentDidUpdate(prevProps: Props, prevState: State) {
    if (prevState.focusedValue !== this.state.focusedValue) {
      this.scrollToFocusedItem();
    }

    if (
      this.props.selected !== undefined &&
      this.props.selected !== prevProps.selected
    ) {
      this.setState({
        value: this.props.selected,
      });
    }
  }

  componentWillUnmount() {
    window.removeEventListener("click", this.onDocumentClick);
    window.removeEventListener("keydown", this.onKeyDown);
  }

  scrollToFocusedItem = () => {
    const focusedItems = this.menuList.getElementsByClassName("is-focused");

    if (focusedItems.length) {
      const focusedItem = focusedItems[0],
        top = focusedItem.offsetTop,
        height = focusedItem.offsetHeight,
        menuScrollTop = this.menuList.scrollTop,
        menuHeight = this.menuList.clientHeight;

      if (top < menuScrollTop) {
        this.menuList.scrollTop = top;
      } else if (top + height > menuScrollTop + menuHeight) {
        this.menuList.scrollTop = top + height - menuHeight;
      }
    }
  };
  onDocumentClick = (event: any) => {
    const { menuOpen } = this.state;
    const target = event.target,
      el = this.rootRef.current;

    if (menuOpen && el && target !== el && !el.contains(target)) {
      this.closeMenu();
    }
  };
  openMenuIfNeeded = () => {
    const { menuOpen } = this.state;

    if (!menuOpen) {
      this.setState({
        menuOpen: true,
      });
    }
  };
  closeMenu = () => {
    this.setState({
      focusedValue: null,
      menuOpen: false,
    });
  };
  onKeyDown = (e: any) => {
    const { focusedValue, hasFocus } = this.state;

    if (hasFocus) {
      switch (e.keyCode) {
        case KeyCodes.ARROW_DOWN:
          e.preventDefault();
          this.openMenuIfNeeded();
          this.focusValue("next");
          break;

        case KeyCodes.ARROW_UP:
          e.preventDefault();
          this.openMenuIfNeeded();
          this.focusValue("previous");
          break;

        case KeyCodes.ENTER:
          if (focusedValue) {
            this.handleAddressItemClick(focusedValue);
          }

          break;

        case KeyCodes.ESC:
          this.closeMenu();
          break;

        case KeyCodes.TAB:
          this.closeMenu();
          break;
      }
    }
  };
  handleBlur = () => {
    const { onBlur } = this.props;
    const { value } = this.state;
    this.setState({
      hasFocus: false,
    });

    if (onBlur) {
      onBlur(value);
    }
  };
  handleFocus = () => {
    this.setState({
      hasFocus: true,
    });
  };
  focusValue = (direction: "next" | "previous") => {
    const { focusedValue } = this.state;
    const { addresses } = this.state;
    const index = addresses.findIndex((address) => focusedValue === address);

    switch (direction) {
      case "next":
        if (index < addresses.length - 1) {
          this.setState({
            focusedValue: addresses[index + 1],
            menuOpen: true,
          });
        }

        break;

      case "previous":
        if (index > 0) {
          this.setState({
            focusedValue: addresses[index - 1],
            menuOpen: true,
          });
        }

        break;
    }
  };
  searchByKeyword = debounce((input: string) => {
    const fetchResults = async (): Promise<Array<Address>> => {
      const url = `${NOMINATIM_URL}/search?${stringifyQuery({
        q: input,
        format: "jsonv2",
        addressdetails: 1,
        countrycodes: "id",
        limit: 15,
        "accept-language": "id",
      })}`;
      const response = await fetch(new Request(url));
      return response.json();
    };

    this.setState({
      isLoading: true,
    });
    fetchResults()
      .then((results) => {
        if (results.length) {
          this.setState({
            addresses: results,
            selectedAddress: results[0],
          });
          this.setState({
            isLoading: false,
          });
        } else {
          this.setState({
            isLoading: false,
          });
        }
      })
      .catch((error) => {
        this.setState({
          isLoading: false,
        });
        console.error(`Failed to fetch by keyword with error ${error}`);
      });
  }, DEBOUNCE_TIME_MILLISECONDS);
  handleOnChange = (e: any) => {
    const { onChange } = this.props;
    const newValue = e.target.value;

    if (newValue && newValue?.length >= MINIMUM_SEARCH_STRING) {
      this.searchByKeyword(newValue);
    }

    if (!newValue || newValue?.length < MINIMUM_SEARCH_STRING) {
      this.setState({
        addresses: [],
      });
    }

    this.setState({
      menuOpen: newValue ? true : false,
      value: newValue,
    });

    if (onChange) {
      onChange(newValue);
    }
  };
  handleAddressItemClick = (address: Address) => {
    const { onChange } = this.props,
      newValue = getStreetAddress(address);
    this.setState({
      value: newValue,
    });
    this.closeMenu();
    this.fetchAddressDetails(address);

    if (onChange) {
      onChange(newValue);
    }

    if (this.input) {
      this.input.focus();
    }
  };
  fetchAddressDetails = (address: Address) => {
    const { addressDetailsCallBack } = this.props;

    if (addressDetailsCallBack) {
      addressDetailsCallBack({
        postalCode: address.address?.postcode || "",
        city: getCity(address),
        country: (address.address?.country_code || "").toUpperCase(),
      });
    }
  };

  render() {
    const { id, name, selected } = this.props;
    const {
      addresses,
      focusedValue,
      isLoading,
      menuOpen,
      selectedAddress,
      value,
    } = this.state;
    return (
      <div
        ref={this.rootRef}
        className={classNames("address-search-input", {
          open: menuOpen,
        })}
      >
        {menuOpen && (
          <LoaderWrapper className="address-input-wrapper">
            <Loader isLoading={isLoading} className="small" />
          </LoaderWrapper>
        )}
        <input
          ref={this.setInputRef}
          autoComplete="off"
          id={id}
          name={name}
          onBlur={this.handleBlur}
          onChange={this.handleOnChange}
          onFocus={this.handleFocus}
          type="text"
          value={selected !== undefined ? selected : value}
        />
        <div
          className={classNames("address-search-input__dropdown", {
            open: menuOpen,
          })}
        >
          <ul ref={this.refMenuListRef}>
            {selectedAddress && !addresses.length && (
              <li className="no-result-item">Alamat tidak ditemukan.</li>
            )}
            {selectedAddress &&
              !!addresses.length &&
              addresses.map((address, index) => {
                const handleClick = () => {
                  this.handleAddressItemClick(address);
                };

                const text = address.display_name;
                return (
                  <li
                    key={index}
                    onClick={handleClick}
                    onKeyDown={(e: React.KeyboardEvent) => {
                      if (e.key === "Enter") handleClick();
                    }}
                    className={classNames("list-item", {
                      "is-focused": focusedValue === address,
                    })}
                  >
                    {text}
                  </li>
                );
              })}
          </ul>
        </div>
      </div>
    );
  }
}

export default AddressSearchInput;
