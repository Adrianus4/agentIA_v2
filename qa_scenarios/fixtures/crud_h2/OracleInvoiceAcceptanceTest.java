package com.agentia.qa.invoice.resource;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.notNullValue;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;

@QuarkusTest
public class OracleInvoiceAcceptanceTest {

    @Test
    public void testIndependentCrudLifecycleAndPersistence() {
        String createBody = "{\"code\":\"INV-QA-901\",\"customerName\":\"Acme Corp\",\"amount\":245.50}";

        Integer createdId = given()
            .contentType("application/json")
            .body(createBody)
            .when()
            .post("/api/invoice")
            .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("code", equalTo("INV-QA-901"))
            .body("customerName", equalTo("Acme Corp"))
            .extract()
            .path("id");

        given()
            .when()
            .get("/api/invoice/" + createdId)
            .then()
            .statusCode(200)
            .body("id", equalTo(createdId))
            .body("code", equalTo("INV-QA-901"))
            .body("customerName", equalTo("Acme Corp"))
            .body("amount", equalTo(245.5f));

        given()
            .when()
            .get("/api/invoice")
            .then()
            .statusCode(200)
            .body("size()", greaterThanOrEqualTo(1));

        String updateBody = "{\"code\":\"INV-QA-901\",\"customerName\":\"Acme Global Ltd\",\"amount\":510.75}";
        given()
            .contentType("application/json")
            .body(updateBody)
            .when()
            .put("/api/invoice/" + createdId)
            .then()
            .statusCode(200)
            .body("customerName", equalTo("Acme Global Ltd"))
            .body("amount", equalTo(510.75f));

        given()
            .when()
            .get("/api/invoice/" + createdId)
            .then()
            .statusCode(200)
            .body("customerName", equalTo("Acme Global Ltd"))
            .body("amount", equalTo(510.75f));

        given()
            .when()
            .delete("/api/invoice/" + createdId)
            .then()
            .statusCode(204);

        given()
            .when()
            .get("/api/invoice/" + createdId)
            .then()
            .statusCode(404);
    }

    @Test
    public void testIndependentNotFoundAndValidationRejections() {
        given()
            .when()
            .get("/api/invoice/777888999")
            .then()
            .statusCode(404);

        given()
            .contentType("application/json")
            .body("{\"code\":\"INV-MISSING\",\"customerName\":\"No Entity\",\"amount\":10.00}")
            .when()
            .put("/api/invoice/777888999")
            .then()
            .statusCode(404);

        given()
            .when()
            .delete("/api/invoice/777888999")
            .then()
            .statusCode(404);

        // Missing required @NotNull fields (code and amount) must be rejected with HTTP 400
        given()
            .contentType("application/json")
            .body("{\"customerName\":\"Incomplete Invoice\"}")
            .when()
            .post("/api/invoice")
            .then()
            .statusCode(400);
    }
}
