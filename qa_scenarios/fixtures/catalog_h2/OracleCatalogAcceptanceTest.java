package com.example.catalog.resource;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.anyOf;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.is;
import static org.hamcrest.CoreMatchers.notNullValue;
import static org.hamcrest.Matchers.greaterThanOrEqualTo;

@QuarkusTest
public class OracleCatalogAcceptanceTest {

    @Test
    public void testUserRegistrationAndUs001Criteria() {
        // US-001: Reject registration without email address
        given()
            .contentType("application/json")
            .body("{\"displayName\":\"No Email User\"}")
            .when()
            .post("/api/user")
            .then()
            .statusCode(400);

        // US-001: Successful registration returns new user identifier
        String validUser = "{\"email\":\"alice.oracle@example.com\",\"displayName\":\"Alice Oracle\"}";
        Integer userId = given()
            .contentType("application/json")
            .body(validUser)
            .when()
            .post("/api/user")
            .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("email", equalTo("alice.oracle@example.com"))
            .body("displayName", equalTo("Alice Oracle"))
            .extract()
            .path("id");

        // US-001: Reject duplicate email address already assigned to another user
        given()
            .contentType("application/json")
            .body("{\"email\":\"alice.oracle@example.com\",\"displayName\":\"Second Alice\"}")
            .when()
            .post("/api/user")
            .then()
            .statusCode(anyOf(is(400), is(409), is(500)));

        // Verify persisted user retrieval & update
        given()
            .when()
            .get("/api/user/" + userId)
            .then()
            .statusCode(200)
            .body("email", equalTo("alice.oracle@example.com"));
    }

    @Test
    public void testProductCatalogCrudAndUs002Criteria() {
        String createProd = "{\"sku\":\"SKU-ORA-100\",\"name\":\"Enterprise Widget\",\"price\":129.95}";
        Integer prodId = given()
            .contentType("application/json")
            .body(createProd)
            .when()
            .post("/api/product")
            .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("sku", equalTo("SKU-ORA-100"))
            .body("name", equalTo("Enterprise Widget"))
            .extract()
            .path("id");

        given()
            .when()
            .get("/api/product")
            .then()
            .statusCode(200)
            .body("size()", greaterThanOrEqualTo(1));

        given()
            .when()
            .get("/api/product/" + prodId)
            .then()
            .statusCode(200)
            .body("sku", equalTo("SKU-ORA-100"))
            .body("name", equalTo("Enterprise Widget"))
            .body("price", equalTo(129.95f));

        given()
            .contentType("application/json")
            .body("{\"sku\":\"SKU-ORA-100\",\"name\":\"Enterprise Widget v2\",\"price\":149.50}")
            .when()
            .put("/api/product/" + prodId)
            .then()
            .statusCode(200)
            .body("name", equalTo("Enterprise Widget v2"))
            .body("price", equalTo(149.5f));

        given()
            .when()
            .delete("/api/product/" + prodId)
            .then()
            .statusCode(204);

        given()
            .when()
            .get("/api/product/" + prodId)
            .then()
            .statusCode(404);
    }
}
