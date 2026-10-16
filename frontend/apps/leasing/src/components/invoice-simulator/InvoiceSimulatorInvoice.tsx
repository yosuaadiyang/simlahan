import React from "react";
import { Row, Column } from "@/components/grid/Grid";
import AmountWithVat from "@/components/vat/AmountWithVat";
import Collapse from "@/components/collapse/Collapse";
import CollapseHeaderSubtitle from "@/components/collapse/CollapseHeaderSubtitle";
import FormText from "@/components/form/FormText";
import FormTitleAndText from "@/components/form/FormTitleAndText";
import InvoiceSimulatorInvoiceRows from "./InvoiceSimulatorInvoiceRows";
import SubTitle from "@/components/content/SubTitle";
import { getContactFullName } from "@/contacts/helpers";
import { formatDate, formatDateRange, getLabelOfOption } from "@/util/helpers";
type Props = {
  billedAmount: number;
  dueDate: string;
  endDate: string;
  receivableTypeOptions: Array<Record<string, any>>;
  recipient: Record<string, any>;
  rows: Array<Record<string, any>>;
  startDate: string;
  type: string;
  typeOptions: Array<Record<string, any>>;
  explanations?: any;
};

const InvoiceSimulatorInvoice = ({
  billedAmount,
  dueDate,
  endDate,
  receivableTypeOptions,
  recipient,
  rows,
  startDate,
  type,
  typeOptions,
}: Props) => {
  return (
    <Collapse
      className="collapse__third"
      defaultOpen={false}
      headerSubtitles={
        <>
          <Column>
            <CollapseHeaderSubtitle>
              {formatDate(dueDate) || "-"}
            </CollapseHeaderSubtitle>
          </Column>
          <Column>
            <CollapseHeaderSubtitle>
              <AmountWithVat amount={billedAmount} date={dueDate} />
            </CollapseHeaderSubtitle>
          </Column>
        </>
      }
      headerTitle={getContactFullName(recipient)}
    >
      <Row>
        <Column small={6} medium={4} large={2}>
          <FormTitleAndText
            title="Periode tagihan"
            text={formatDateRange(startDate, endDate)}
          />
        </Column>
        <Column small={6} medium={4} large={2}>
          <FormTitleAndText title="Jatuh tempo" text={formatDate(dueDate)} />
        </Column>
        <Column small={6} medium={4} large={2}>
          <FormTitleAndText
            title="Jumlah"
            text={<AmountWithVat amount={billedAmount} date={dueDate} />}
          />
        </Column>
        <Column small={6} medium={4} large={2}>
          <FormTitleAndText
            title="Jenis"
            text={getLabelOfOption(typeOptions, type)}
          />
        </Column>
      </Row>

      <SubTitle>Rincian</SubTitle>
      {!rows.length && <FormText>Tidak ada baris</FormText>}
      {!!rows.length && (
        <InvoiceSimulatorInvoiceRows
          dueDate={dueDate}
          receivableTypeOptions={receivableTypeOptions}
          rows={rows}
        />
      )}
    </Collapse>
  );
};

export default InvoiceSimulatorInvoice;
