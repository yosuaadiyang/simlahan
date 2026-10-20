import { combineReducers } from "redux";
import { handleActions } from "redux-actions";
import type { Attributes, Methods, Reducer } from "types";
import type {
  UiDataList,
  ReceiveAttributesAction,
  ReceiveMethodsAction,
  ReceiveUiDataListAction,
} from "@/uiData/types";
const isFetchingAttributesReducer: Reducer<boolean> = handleActions(
  {
    "mvj/uiData/FETCH_ATTRIBUTES": () => true,
    "mvj/uiData/RECEIVE_METHODS": () => false,
    "mvj/uiData/ATTRIBUTES_NOT_FOUND": () => false,
  },
  false,
);
const attributesReducer: Reducer<Attributes> = handleActions(
  {
    "mvj/uiData/RECEIVE_ATTRIBUTES": (
      state: Attributes,
      { payload }: ReceiveAttributesAction,
    ) => {
      return payload;
    },
  },
  null,
);
const methodsReducer: Reducer<Methods> = handleActions(
  {
    "mvj/uiData/RECEIVE_METHODS": (
      state: Methods,
      { payload }: ReceiveMethodsAction,
    ) => {
      return payload;
    },
  },
  null,
);
const isFetchingReducer: Reducer<boolean> = handleActions(
  {
    "mvj/uiData/FETCH_ALL": () => true,
    "mvj/uiData/CREATE": () => true,
    "mvj/uiData/DELETE": () => true,
    "mvj/uiData/EDIT": () => true,
    "mvj/uiData/RECEIVE_ALL": () => false,
    "mvj/uiData/NOT_FOUND": () => false,
  },
  false,
);
// Tabel kosong tetap dihitung sudah dimuat agar daftar kosong tidak diminta berulang tanpa henti.
const isFetchedReducer: Reducer<boolean> = handleActions(
  {
    "mvj/uiData/RECEIVE_ALL": () => true,
    "mvj/uiData/NOT_FOUND": () => true,
  },
  false,
);
const listReducer: Reducer<UiDataList> = handleActions(
  {
    "mvj/uiData/RECEIVE_ALL": (
      state: UiDataList,
      { payload }: ReceiveUiDataListAction,
    ) => {
      return payload;
    },
  },
  [],
);
export default combineReducers<Record<string, any>, any>({
  attributes: attributesReducer,
  isFetched: isFetchedReducer,
  isFetching: isFetchingReducer,
  isFetchingAttributes: isFetchingAttributesReducer,
  list: listReducer,
  methods: methodsReducer,
});
