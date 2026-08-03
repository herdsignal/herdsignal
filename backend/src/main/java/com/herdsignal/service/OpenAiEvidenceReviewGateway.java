package com.herdsignal.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.herdsignal.config.EvidenceReviewProperties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@Component
@RequiredArgsConstructor
public class OpenAiEvidenceReviewGateway implements EvidenceReviewGateway {
    private static final URI RESPONSES_URI = URI.create("https://api.openai.com/v1/responses");
    private static final String INSTRUCTIONS = """
            당신은 HerdSignal의 장기 운용 연구용 근거 검토기다. 제공된 evidence 배열만 사용한다.
            evidence에 없는 사실, 뉴스, 가격 전망, 매수·매도 결론을 만들지 않는다.
            BUSINESS_HEALTH, EXPECTATION_VALUATION, MARKET_SECTOR, CHART_CROWD,
            INFORMATION_CHANGE 관점은 같은 area의 AVAILABLE 근거만 인용한다.
            RED_TEAM만 여러 영역의 근거를 대조할 수 있다. 각 주장에는 evidence ID를
            연결하고, AVAILABLE 근거가 없으면 의견을 만들지 말고 missingEvidence에 적는다.
            HERD는 상태 관찰값이며 행동 신호가 아니다. 최종 행동은 반드시 HOLD 0%이고
            directionPrediction은 false다. 짧고 중립적인 한국어로 작성한다.
            """;
    private static final String SCHEMA = """
            {
              "type":"object",
              "additionalProperties":false,
              "properties":{
                "lenses":{"type":"array","minItems":6,"maxItems":6,"items":{
                  "type":"object","additionalProperties":false,
                  "properties":{
                    "code":{"type":"string","enum":["BUSINESS_HEALTH","EXPECTATION_VALUATION","MARKET_SECTOR","CHART_CROWD","INFORMATION_CHANGE","RED_TEAM"]},
                    "stance":{"type":"string","enum":["SUPPORTIVE","NEUTRAL","CAUTION","INSUFFICIENT"]},
                    "summary":{"type":"string"},
                    "evidenceIds":{"type":"array","items":{"type":"string"}},
                    "missingEvidence":{"type":"array","items":{"type":"string"}}
                  },
                  "required":["code","stance","summary","evidenceIds","missingEvidence"]
                }},
                "summary":{"type":"string"},
                "disagreements":{"type":"array","items":{"type":"string"}},
                "factsToVerify":{"type":"array","items":{"type":"string"}},
                "directionPrediction":{"type":"boolean","enum":[false]},
                "operationalAction":{"type":"string","enum":["HOLD"]},
                "operationalActionRatio":{"type":"number","enum":[0]}
              },
              "required":["lenses","summary","disagreements","factsToVerify","directionPrediction","operationalAction","operationalActionRatio"]
            }
            """;

    private final ObjectMapper objectMapper;
    private final EvidenceReviewProperties properties;

    @Override
    public boolean isEnabled() {
        return properties.isEnabled()
                && properties.getApiKey() != null
                && !properties.getApiKey().isBlank();
    }

    @Override
    public String model() {
        return properties.getModel();
    }

    @Override
    public Draft review(Packet packet, String safetyIdentifier) {
        if (!isEnabled()) {
            throw new IllegalStateException("AI 근거 분석이 비활성화되어 있습니다.");
        }
        try {
            ObjectNode body = objectMapper.createObjectNode();
            body.put("model", properties.getModel());
            body.put("store", false);
            body.put("safety_identifier", safetyIdentifier);
            body.put("max_output_tokens", 1800);
            ArrayNode input = body.putArray("input");
            input.addObject().put("role", "developer").put("content", INSTRUCTIONS);
            input.addObject().put("role", "user").put(
                    "content", objectMapper.writeValueAsString(packet)
            );
            ObjectNode format = body.putObject("text").putObject("format");
            format.put("type", "json_schema");
            format.put("name", "herd_evidence_review");
            format.put("strict", true);
            format.set("schema", objectMapper.readTree(SCHEMA));

            HttpRequest request = HttpRequest.newBuilder(RESPONSES_URI)
                    .timeout(properties.getTimeout())
                    .header("Authorization", "Bearer " + properties.getApiKey())
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(body)))
                    .build();
            HttpResponse<String> response = HttpClient.newBuilder()
                    .connectTimeout(properties.getTimeout())
                    .build()
                    .send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException("OpenAI 응답 상태: " + response.statusCode());
            }
            String outputText = extractOutputText(objectMapper.readTree(response.body()));
            return objectMapper.readValue(outputText, Draft.class);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("AI 근거 분석 요청이 중단되었습니다.", exception);
        } catch (Exception exception) {
            throw new IllegalStateException("AI 근거 분석 요청에 실패했습니다.", exception);
        }
    }

    private String extractOutputText(JsonNode response) {
        for (JsonNode output : response.path("output")) {
            if (!"message".equals(output.path("type").asText())) continue;
            for (JsonNode content : output.path("content")) {
                if ("output_text".equals(content.path("type").asText())) {
                    String text = content.path("text").asText();
                    if (!text.isBlank()) return text;
                }
            }
        }
        throw new IllegalStateException("구조화된 output_text가 없습니다.");
    }
}
