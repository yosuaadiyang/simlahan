import { describe, expect, it } from "vitest";
import applicationReducer, {
  attributesNotFound,
  fetchAttachmentAttributes,
  fetchAttributes,
  receiveAttachmentAttributes,
  receiveAttributes,
  receiveFormAttributes,
  receiveMethods,
  initialState,
} from "./slice";
import mockFormAttributes from "./form-attributes-mock-data.json";
import {
  companyIdentifierValidator,
  emailValidator,
  personalIdentifierValidator,
  validateApplicationForm,
} from "./formValidation";
import { getFieldChoicesSorted } from "./helpers";
import { APPLICANT_TYPE_FIELD_IDENTIFIER } from "./constants";
import { get } from "lodash-es";
describe("Application", () => {
  describe("getFieldChoicesSorted", () => {
    it("sorts applicant types without mutating the source choices", () => {
      const choices = [{ value: "2" }, { value: "1" }];

      const sortedChoices = getFieldChoicesSorted(
        { identifier: APPLICANT_TYPE_FIELD_IDENTIFIER } as any,
        choices as any,
      );

      expect(sortedChoices.map(({ value }) => value)).to.deep.equal(["1", "2"]);
      expect(choices.map(({ value }) => value)).to.deep.equal(["2", "1"]);
    });
  });
  describe("Reducer", () => {
    describe("applicationReducer", () => {
      it("should update isFetchingAttributes flag to true", () => {
        const newState = { ...initialState, isFetchingAttributes: true };
        const state = applicationReducer(initialState, fetchAttributes());
        expect(state).to.deep.equal(newState);
      });
      it("should update attributes", () => {
        const dummyAttributes = {
          id: 1,
          label: "Foo",
          name: "Bar",
        };
        const newState = {
          ...initialState,
          attributes: dummyAttributes,
          isFetchingAttributes: false,
        };
        const state = applicationReducer(
          initialState,
          receiveAttributes(dummyAttributes),
        );
        expect(state).to.deep.equal(newState);
      });
      it("should update methods", () => {
        const dummyMethods = {
          PATCH: true,
          DELETE: true,
          GET: true,
          HEAD: true,
          POST: true,
          OPTIONS: true,
          PUT: true,
        };
        const newState = { ...initialState, methods: dummyMethods };
        const state = applicationReducer(
          initialState,
          receiveMethods(dummyMethods),
        );
        expect(state).to.deep.equal(newState);
      });
      it("should update isFetchingAttributes flag to false by attributesNotFound", () => {
        const newState = { ...initialState, isFetchingAttributes: false };
        let state = applicationReducer(initialState, fetchAttributes());
        state = applicationReducer(state, attributesNotFound());
        expect(state).to.deep.equal(newState);
      });
      it("should update isFetchingAttachmentAttributes flag to true", () => {
        const newState = {
          ...initialState,
          isFetchingAttachmentAttributes: true,
        };
        const state = applicationReducer(
          initialState,
          fetchAttachmentAttributes(),
        );
        expect(state).to.deep.equal(newState);
      });
      it("should update attachment attributes", () => {
        const dummyAttributes = {
          id: 1,
          label: "Foo",
          name: "Bar",
        };
        const newState = {
          ...initialState,
          attachmentAttributes: dummyAttributes,
          isFetchingAttachmentAttributes: false,
        };
        const state = applicationReducer(
          { ...initialState },
          receiveAttachmentAttributes(dummyAttributes),
        );
        expect(state).to.deep.equal(newState);
      });
    });
    it("should update form attributes", () => {
      const newState = {
        ...initialState,
        formAttributes: mockFormAttributes,
        isFetchingFormAttributes: false,
      };
      const state = applicationReducer(
        { ...initialState, isFetchingFormAttributes: true },
        receiveFormAttributes(mockFormAttributes),
      );
      expect(state).to.deep.equal(newState);
    });
  });
  describe("validators", () => {
    describe("personalIdentifierValidator (NIK)", () => {
      it("should ignore an empty identifier", () => {
        expect(personalIdentifierValidator("", "fail")).to.not.exist;
      });
      it("should not accept a non-string value", () => {
        expect(
          personalIdentifierValidator({ nik: "2171010101900001" }, "fail"),
        ).to.equal("fail");
      });
      it("should accept a valid NIK (male)", () => {
        expect(personalIdentifierValidator("2171011501900001", "fail")).to.not
          .exist;
      });
      it("should accept a valid NIK (female, day + 40)", () => {
        expect(personalIdentifierValidator("2171015501900002", "fail")).to.not
          .exist;
      });
      it("should not accept a NIK with wrong length", () => {
        expect(personalIdentifierValidator("217101150190001", "fail")).to.equal(
          "fail",
        );
        expect(
          personalIdentifierValidator("21710115019000011", "fail"),
        ).to.equal("fail");
      });
      it("should not accept letters", () => {
        expect(
          personalIdentifierValidator("21710115019000A1", "fail"),
        ).to.equal("fail");
      });
      it("should not accept an impossible birth date", () => {
        expect(
          personalIdentifierValidator("2171013213900001", "fail"),
        ).to.equal("fail");
        expect(
          personalIdentifierValidator("2171017201900001", "fail"),
        ).to.equal("fail");
      });
      it("should not accept a zero region or sequence", () => {
        expect(
          personalIdentifierValidator("0071011501900001", "fail"),
        ).to.equal("fail");
        expect(
          personalIdentifierValidator("2171011501900000", "fail"),
        ).to.equal("fail");
      });
    });
    describe("companyIdentifierValidator (NPWP)", () => {
      it("should ignore an empty identifier", () => {
        expect(companyIdentifierValidator("", "fail")).to.not.exist;
      });
      it("should not accept a non-string value", () => {
        expect(
          companyIdentifierValidator({ npwp: "012345678901000" }, "fail"),
        ).to.equal("fail");
      });
      it("should accept a 15 digit NPWP", () => {
        expect(companyIdentifierValidator("012345678901000", "fail")).to.not
          .exist;
      });
      it("should accept a formatted 15 digit NPWP", () => {
        expect(companyIdentifierValidator("01.234.567.8-901.000", "fail")).to
          .not.exist;
      });
      it("should accept a 16 digit NPWP", () => {
        expect(companyIdentifierValidator("2171011501900001", "fail")).to.not
          .exist;
      });
      it("should not accept invalid lengths or formats", () => {
        expect(companyIdentifierValidator("0346848-5", "fail")).to.equal(
          "fail",
        );
        expect(companyIdentifierValidator("01234567890100", "fail")).to.equal(
          "fail",
        );
        expect(companyIdentifierValidator("01.234.567.8-901", "fail")).to.equal(
          "fail",
        );
      });
    });
    describe("emailValidator", () => {
      it("should accept a regular email address", () => {
        const error = emailValidator("example@gmail.com", "fail");
        expect(error).to.not.exist;
      });
      it("should accept a plus alias email address", () => {
        const error = emailValidator("example+mvj@gmail.com", "fail");
        expect(error).to.not.exist;
      });
      it("should accept multiple dots on each side", () => {
        const error = emailValidator(
          "example.user.of.the.mvj.service@gmail.by.google.com",
          "fail",
        );
        expect(error).to.not.exist;
      });
      it("should not accept an email address without anything before the at sign", () => {
        const error = emailValidator("@gmail.com", "fail");
        expect(error).to.equal("fail");
      });
      it("should not accept an email address without anything after the at sign", () => {
        const error = emailValidator("example@", "fail");
        expect(error).to.equal("fail");
      });
      it("should not accept an email address without an at sign", () => {
        const error = emailValidator("example.gmail.com", "fail");
        expect(error).to.equal("fail");
      });
      it("should not accept an email address with a space in it", () => {
        const error = emailValidator("example @gmail.com", "fail");
        expect(error).to.equal("fail");
      });
      it("should not accept an email address without a top level domain", () => {
        const error = emailValidator("example@gmail", "fail");
        expect(error).to.equal("fail");
      });
      it("should not accept an email address with a one-letter top level domain", () => {
        const error = emailValidator("example@gmail.c", "fail");
        expect(error).to.equal("fail");
      });
    });
    describe("validateApplicationForm", () => {
      it("should accept a simple form with a singular control value at a 100% ratio", () => {
        const error = validateApplicationForm("formEntries")({
          formEntries: {
            sections: {
              test: [
                {
                  fields: {
                    hallintaosuus: {
                      value: "1 / 1",
                      extraValue: "",
                    },
                  },
                },
              ],
            },
          },
        });
        expect(Object.keys(error).length).to.be.equal(0);
      });
      it("should accept a simple form with multiple control values equaling a 100% ratio in total", () => {
        const error = validateApplicationForm("formEntries")({
          formEntries: {
            sections: {
              test: [
                {
                  fields: {
                    hallintaosuus: {
                      value: "1 / 7",
                      extraValue: "",
                    },
                  },
                },
                {
                  fields: {
                    hallintaosuus: {
                      value: "18 / 21",
                      extraValue: "",
                    },
                  },
                },
              ],
            },
          },
        });
        expect(Object.keys(error).length).to.be.equal(0);
      });
      it("should not accept a simple form with multiple control values not equaling a 100% ratio in total", () => {
        const error = validateApplicationForm("formEntries")({
          formEntries: {
            sections: {
              test: [
                {
                  fields: {
                    hallintaosuus: {
                      value: "3 / 8",
                      extraValue: "",
                    },
                  },
                },
                {
                  fields: {
                    hallintaosuus: {
                      value: "4 / 8",
                      extraValue: "",
                    },
                  },
                },
              ],
            },
          },
        });
        expect(
          get(error, "formEntries.sections.test[0].fields.hallintaosuus.value"),
        ).to.equal("Total porsi penguasaan harus 100%");
        expect(
          get(error, "formEntries.sections.test[1].fields.hallintaosuus.value"),
        ).to.equal("Total porsi penguasaan harus 100%");
      });
      it("should not care about unrelated fractional fields when validating the control share ratio", () => {
        const error = validateApplicationForm("formEntries")({
          formEntries: {
            sections: {
              test: [
                {
                  fields: {
                    hallintaosuus: {
                      value: "9 / 9",
                      extraValue: "",
                    },
                    arvostelu: {
                      value: "5 / 7",
                      extraValue: "",
                    },
                  },
                },
              ],
            },
          },
        });
        expect(Object.keys(error).length).to.be.equal(0);
      });
    });
  });
});
