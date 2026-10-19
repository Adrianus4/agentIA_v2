package com.agentia.qa.inventory.resource;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.notNullValue;

@QuarkusTest
public class OracleInventoryServiceAcceptanceTest {

    @Test
    public void testStockItemCrudAndNotFound() {
        Integer id = given()
            .contentType("application/json")
            .body("{\"itemCode\":\"ITM-SOL-202\",\"warehouseName\":\"Central Hub\"}")
            .when()
            .post("/api/stockitem")
            .then()
            .statusCode(201)
            .body("id", notNullValue())
            .body("itemCode", equalTo("ITM-SOL-202"))
            .extract()
            .path("id");

        given()
            .when()
            .get("/api/stockitem/" + id)
            .then()
            .statusCode(200)
            .body("itemCode", equalTo("ITM-SOL-202"))
            .body("warehouseName", equalTo("Central Hub"));

        given()
            .when()
            .delete("/api/stockitem/" + id)
            .then()
            .statusCode(204);

        given()
            .when()
            .get("/api/stockitem/" + id)
            .then()
            .statusCode(404);
    }
}
