import callApi from "./callApi";
import { SERVER_ERROR_MESSAGE } from "./responseBody";

function* callApiPaginated(request: Request): Generator<any, any, any> {
  let { response, bodyAsJson } = yield callApi(request);
  if (response.status !== 200) {
    // Galat halaman pertama diteruskan apa adanya ke pemanggil.
    return { response, bodyAsJson };
  }
  const allResults = [...bodyAsJson.results];

  if (bodyAsJson.next) {
    let nextUrl = bodyAsJson.next;
    while (nextUrl !== null) {
      request = new Request(nextUrl, {
        method: "GET",
      });
      ({ response, bodyAsJson } = yield callApi(request));
      const status = response.status;

      switch (status) {
        case 200:
          allResults.push(...bodyAsJson.results);
          break;
        case 204:
          return {
            response,
          };
        default:
          return {
            response,
            bodyAsJson: {
              exception: response.status,
              message:
                bodyAsJson?.detail ||
                bodyAsJson?.message ||
                SERVER_ERROR_MESSAGE,
            },
          };
      }

      nextUrl = bodyAsJson.next || null;
    }
  }

  bodyAsJson.results = allResults;

  return { response, bodyAsJson };
}

export default callApiPaginated;
