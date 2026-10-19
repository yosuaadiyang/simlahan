import { describe, expect, it } from "vitest";
import ErrorIcon from "@/components/icons/ErrorIcon";
import SuccessIcon from "@/components/icons/SuccessIcon";
import SubMenu from "@/components/sideMenu/SubMenu";
import { HDS_SELECT_TEXTS } from "@/components/hdsSelectTexts";

describe("components", () => {
  describe("ErrorIcon", () => {
    it("should return ErrorIcon", () => {
      const errorIcon: any = ErrorIcon({
        className: "error",
      });
      expect(errorIcon.props.className).to.deep.equal(
        "icons icons__error error",
      );
    });
  });
  describe("SuccessIcon", () => {
    it("should return SuccessIcon", () => {
      const successIcon: any = SuccessIcon({
        className: "success",
      });
      expect(successIcon.props.className).to.deep.equal(
        "icons icons__success success",
      );
    });
  });
  describe("SubMenu", () => {
    const props = {
      header: "Lainnya",
      isOpen: false,
      menuKey: "tools",
      onHeaderClick: () => {},
    };
    it("should not render a header without any allowed item", () => {
      const subMenu = new SubMenu({
        ...props,
        items: [{ allow: false, text: "Indeks", to: "/indeks" }],
      });
      expect(subMenu.render()).toBeNull();
    });
    it("should render when an item is allowed", () => {
      const subMenu = new SubMenu({
        ...props,
        items: [{ allow: true, text: "Indeks", to: "/indeks" }],
      });
      expect(subMenu.render()).not.toBeNull();
    });
  });
  describe("HDS_SELECT_TEXTS", () => {
    it("should override the English select texts", () => {
      const { language, ...texts } = HDS_SELECT_TEXTS;
      expect(language).toBe("en");
      expect(texts).not.toHaveProperty("placeholder");
      Object.values(texts).forEach((text) => {
        expect(text).not.toMatch(
          /\b(Remove|Clear|Show|selected|options?|Found|Try)\b/,
        );
      });
    });
  });
});
