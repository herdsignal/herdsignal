package com.herdsignal.dto;

import java.time.LocalDate;
import java.util.List;

/** 보유·관심종목에서 파생한 계정별 State S1 변화함. */
public record ObservationChangesResponse(
        LocalDate generatedThrough,
        int trackedTickerCount,
        int unreadCount,
        List<ObservationChangeEvent> events,
        List<ProvisionalObservationAttention> provisionalAttention
) {}
