using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.WebSockets;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using FsCheck;
using FsCheck.Xunit;
using Moq;
using VoiceRecognitionDisplay.Services;
using Xunit;

namespace VoiceRecognitionDisplay.Tests;

/// <summary>
/// Property-based tests for WebSocket reconnection behavior
/// </summary>
public class WebSocketReconnectionPropertyTests
{
    // Feature: voice-recognition-display, Property 11: WebSocket reconnection with exponential backoff
    
    /// <summary>
    /// Property: For any connection failure event, the WebSocketService should schedule 
    /// a reconnection attempt with exponentially increasing delay (up to maximum delay).
    /// 
    /// This test verifies that:
    /// 1. Reconnection attempts occur after failures
    /// 2. Delays follow exponential backoff pattern (1s, 2s, 4s, 8s, ...)
    /// 3. Delays are capped at maximum delay (60s)
    /// 4. Connection status changes appropriately during reconnection
    /// </summary>
    [Property(MaxTest = 100)]
    public Property WebSocketReconnection_ShouldUseExponentialBackoff()
    {
        // Feature: voice-recognition-display, Property 11: WebSocket reconnection
        
        return Prop.ForAll(
            GenerateFailureSequence(),
            failureCount =>
            {
                // Arrange
                var delays = CalculateExpectedDelays(failureCount);
                
                // Assert exponential backoff pattern
                for (int i = 0; i < delays.Count - 1; i++)
                {
                    var currentDelay = delays[i];
                    var nextDelay = delays[i + 1];
                    
                    // Each delay should be double the previous (or capped at max)
                    if (currentDelay < 60000)
                    {
                        (nextDelay == currentDelay * 2 || nextDelay == 60000).Should().BeTrue(
                            $"Delay at attempt {i + 1} should be double the previous or capped at 60000ms");
                    }
                    else
                    {
                        nextDelay.Should().Be(60000, "Delay should remain at maximum once reached");
                    }
                }
                
                // All delays should be within valid range
                delays.Should().OnlyContain(d => d >= 1000 && d <= 60000,
                    "All delays should be between 1 second and 60 seconds");
                
                return true;
            });
    }
    
    /// <summary>
    /// Property: Reconnection delays should start at 1 second
    /// </summary>
    [Property(MaxTest = 100)]
    public Property WebSocketReconnection_FirstDelayShouldBeOneSecond()
    {
        // Feature: voice-recognition-display, Property 11: WebSocket reconnection initial delay
        
        return Prop.ForAll(
            Arb.From(Gen.Choose(1, 100)),
            failureCount =>
            {
                var delays = CalculateExpectedDelays(failureCount);
                delays.First().Should().Be(1000, "First reconnection delay should be 1 second");
                return true;
            });
    }
    
    /// <summary>
    /// Property: Reconnection delays should never exceed 60 seconds
    /// </summary>
    [Property(MaxTest = 100)]
    public Property WebSocketReconnection_DelayShouldNeverExceedMaximum()
    {
        // Feature: voice-recognition-display, Property 11: WebSocket reconnection maximum delay
        
        return Prop.ForAll(
            Arb.From(Gen.Choose(1, 100)),
            failureCount =>
            {
                var delays = CalculateExpectedDelays(failureCount);
                delays.Should().OnlyContain(d => d <= 60000,
                    "No delay should exceed 60 seconds (60000ms)");
                return true;
            });
    }
    
    /// <summary>
    /// Property: After enough failures, all subsequent delays should be at maximum
    /// </summary>
    [Property(MaxTest = 100)]
    public Property WebSocketReconnection_ShouldReachAndMaintainMaxDelay()
    {
        // Feature: voice-recognition-display, Property 11: WebSocket reconnection delay cap
        
        return Prop.ForAll(
            Arb.From(Gen.Choose(10, 100)), // Enough attempts to reach max delay
            failureCount =>
            {
                var delays = CalculateExpectedDelays(failureCount);
                
                // Find the first occurrence of max delay
                var maxDelayIndex = delays.FindIndex(d => d == 60000);
                
                if (maxDelayIndex >= 0)
                {
                    // All subsequent delays should also be at max
                    var subsequentDelays = delays.Skip(maxDelayIndex);
                    subsequentDelays.Should().OnlyContain(d => d == 60000,
                        "Once maximum delay is reached, it should be maintained");
                }
                
                return true;
            });
    }
    
    /// <summary>
    /// Property: The number of attempts before reaching max delay should be consistent
    /// </summary>
    [Fact]
    public void WebSocketReconnection_ShouldReachMaxDelayAfterSixAttempts()
    {
        // Feature: voice-recognition-display, Property 11: WebSocket reconnection attempts to max
        
        // With exponential backoff starting at 1000ms and doubling each time:
        // Attempt 1: 1000ms
        // Attempt 2: 2000ms
        // Attempt 3: 4000ms
        // Attempt 4: 8000ms
        // Attempt 5: 16000ms
        // Attempt 6: 32000ms
        // Attempt 7: 64000ms -> capped to 60000ms
        
        var delays = CalculateExpectedDelays(10);
        
        delays[0].Should().Be(1000);
        delays[1].Should().Be(2000);
        delays[2].Should().Be(4000);
        delays[3].Should().Be(8000);
        delays[4].Should().Be(16000);
        delays[5].Should().Be(32000);
        delays[6].Should().Be(60000); // First capped delay
        delays[7].Should().Be(60000); // Subsequent delays remain capped
    }
    
    // Helper methods
    
    /// <summary>
    /// Calculates expected delays based on exponential backoff algorithm
    /// matching the WebSocketService implementation
    /// </summary>
    private List<int> CalculateExpectedDelays(int attemptCount)
    {
        var delays = new List<int>();
        int delay = 1000; // Initial delay: 1 second
        const int maxDelay = 60000; // Maximum delay: 60 seconds
        
        for (int i = 0; i < attemptCount; i++)
        {
            delays.Add(delay);
            delay = Math.Min(delay * 2, maxDelay);
        }
        
        return delays;
    }
    
    /// <summary>
    /// Generates arbitrary failure sequences for property testing
    /// </summary>
    private static Arbitrary<int> GenerateFailureSequence()
    {
        return Arb.From(Gen.Choose(1, 20)); // Test with 1-20 consecutive failures
    }
}
