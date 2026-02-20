#!/usr/bin/env bash

MODEL="mistral"
URL="http://localhost:11434/api/generate"

PROMPT="Explain how a combustion engine works in detail."

TOKEN_SIZES=(50 100 200 400 800)

printf "\n%-10s %-15s %-20s %-20s\n" \
  "Tokens" "Total Time (s)" "Generated Tokens" "Time per Token (ms)"

printf "%s\n" "---------------------------------------------------------------------------------------"

for TOKENS in "${TOKEN_SIZES[@]}"; do
    START=$(date +%s.%N)

    RESPONSE=$(curl -s $URL \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"$MODEL\",
            \"prompt\": \"$PROMPT\",
            \"stream\": false,
            \"options\": {
                \"num_predict\": $TOKENS
            }
        }")

    END=$(date +%s.%N)
    TOTAL_TIME=$(echo "$END - $START" | bc)

    GENERATED=$(echo "$RESPONSE" | jq '.eval_count')

    if [ "$GENERATED" -gt 0 ]; then
        TIME_PER_TOKEN=$(echo "($TOTAL_TIME / $GENERATED) * 1000" | bc -l)
    else
        TIME_PER_TOKEN=0
    fi

    printf "%-10s %-15.3f %-20s %-20.3f\n" \
        "$TOKENS" "$TOTAL_TIME" "$GENERATED" "$TIME_PER_TOKEN"
done

echo ""
