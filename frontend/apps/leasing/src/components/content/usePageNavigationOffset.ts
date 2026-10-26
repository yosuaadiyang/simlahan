import { useEffect } from "react";
import type { RefObject } from "react";

/**
 * Bilah kontrol/tab halaman (content__page-navigator-wrapper) melayang tetap di
 * bawah bilah atas. Konten halaman digeser setinggi bilah itu, dan ikut
 * menyesuaikan saat tingginya berubah (mis. tombol pindah baris di HP).
 */
const usePageNavigationOffset = (
  ref: RefObject<HTMLElement | null>,
): void => {
  useEffect(() => {
    const apply = () => {
      const navigation = document.getElementsByClassName(
        "content__page-navigator-wrapper",
      )[0];
      const rect = navigation?.getClientRects()[0];

      if (rect && ref.current) {
        ref.current.style.marginTop = rect.height + "px";
      }
    };

    window.addEventListener("resize", apply);
    const navigation = document.getElementsByClassName(
      "content__page-navigator-wrapper",
    )[0];
    const observer =
      navigation && typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(apply)
        : null;
    observer?.observe(navigation);

    return () => {
      window.removeEventListener("resize", apply);
      observer?.disconnect();
    };
  }, [ref]);
};

export default usePageNavigationOffset;
