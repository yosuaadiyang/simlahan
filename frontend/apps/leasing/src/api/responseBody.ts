/** Pesan untuk galat server yang tidak membawa isi JSON. */
export const SERVER_ERROR_MESSAGE =
  "Terjadi galat pada server. Coba lagi beberapa saat lagi atau hubungi administrator.";
export const INVALID_RESPONSE_MESSAGE =
  "Jawaban server tidak dapat dibaca. Coba lagi beberapa saat lagi.";

/**
 * Baca isi jawaban API sebagai JSON. Halaman galat HTML (mis. 502 dari proxy)
 * atau isi kosong tidak boleh memunculkan galat parser ke pengguna.
 */
export const readResponseBody = async (response: Response): Promise<any> => {
  if (response.status === 204) {
    return {};
  }
  if (response.status === 500) {
    return {
      exception: response.status,
      message: SERVER_ERROR_MESSAGE,
    };
  }
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch {
    return {
      exception: response.status,
      message:
        response.status >= 500
          ? SERVER_ERROR_MESSAGE
          : INVALID_RESPONSE_MESSAGE,
    };
  }
};
