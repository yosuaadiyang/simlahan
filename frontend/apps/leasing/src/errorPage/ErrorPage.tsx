import React from "react";
import { Row, Column } from "@/components/grid/Grid";

const ErrorPage = () => (
  <div className="error-page">
    <Row>
      <Column>
        <h1>404</h1>
        <p>Halaman yang Anda cari tidak ada</p>
      </Column>
    </Row>
  </div>
);

export default ErrorPage;
