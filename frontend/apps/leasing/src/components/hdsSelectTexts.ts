/**
 * Teks bahasa Indonesia untuk Select HDS. HDS hanya mengenal bahasa fi/sv/en;
 * "en" dipakai sebagai cadangan dan semua teks yang tampil atau dibacakan
 * pembaca layar ditimpa di sini.
 */
export const HDS_SELECT_TEXTS = {
  language: "en",
  clearButtonAriaLabel_one: 'Hapus pilihan "{{label}}".',
  clearButtonAriaLabel_multiple: "Hapus semua {{selectionCount}} pilihan.",
  noSelectedOptions: "Tidak ada pilihan",
  required: "Wajib diisi.",
  selectedOptionsCount_zero: "{{selectionCount}} pilihan",
  selectedOptionsCount_one: "{{selectionCount}} pilihan",
  selectedOptionsCount_multiple: "{{selectionCount}} pilihan",
  selectedOptionsCount_and: "dan",
  selectedOptionsCount_otherOptions: "pilihan lain",
  multiSelectGroupAriaLabel: "{{label}} (pilih semua)",
  tagsClearAllButton: "Hapus semua",
  tagsClearAllButtonAriaLabel_one: 'Hapus pilihan "{{label}}".',
  tagsClearAllButtonAriaLabel_multiple:
    "Hapus semua {{selectionCount}} pilihan.",
  tagsRemaining_one: "Tersisa satu pilihan.",
  tagsRemaining_multiple: "Tersisa {{selectionCount}} pilihan.",
  tagRemoved: 'Pilihan "{{value}}" dihapus.',
  tagRemoveSelectionAriaLabel: 'Hapus pilihan "{{label}}".',
  tagsPartiallyHidden: "Sebagian pilihan disembunyikan.",
  tagsShowAllButton: "Tampilkan semua ({{selectionCount}})",
  tagsShowLessButton: "Tampilkan lebih sedikit",
  tagsShowAllButtonAriaLabel: "Tampilkan semua {{selectionCount}} pilihan.",
  tagsShowLessButtonAriaLabel: "Tampilkan lebih sedikit pilihan.",
  filterLabel: "Saring",
  filterPlaceholder: "Ketik untuk menyaring pilihan",
  filterClearButtonAriaLabel: "Hapus saringan",
  filteredWithoutResultsInfo: 'Tidak ada pilihan untuk "{{value}}".',
  filterWithAnotherTerm: "Coba kata lain.",
  filterResults: 'Hasil saringan untuk "{{value}}".',
  filterResultsCount_one: "Ditemukan 1 pilihan.",
  filterResultsCount_multiple: "Ditemukan {{numberIndicator}} pilihan.",
  choiceCount_one: "Satu pilihan.",
  choiceCount_multiple: "{{numberIndicator}} pilihan.",
  searchLabel: "Cari",
  searchPlaceholder: "Ketik untuk mencari pilihan",
  searchClearButtonAriaLabel: "Hapus pencarian",
  searchedWithoutResultsInfo: 'Tidak ada pilihan untuk "{{value}}".',
  searchWithAnotherTerm: "Coba kata lain.",
  searchErrorTitle: "Pilihan tidak dapat dimuat.",
  searchErrorText:
    "Coba lagi atau hubungi administrator bila masalah berlanjut.",
  searching: 'Mencari "{{value}}".',
  searchResults_one: 'Ditemukan satu pilihan untuk "{{value}}".',
  searchResults_multiple:
    'Ditemukan {{numberIndicator}} pilihan untuk "{{value}}".',
} as const;
