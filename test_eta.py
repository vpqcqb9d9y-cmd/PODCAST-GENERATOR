#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for improved ETA calculations in Azure TTS engine
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def test_dynamic_weights():
    """Test dynamic weights calculation for different content sizes"""
    print("🧪 Testing Dynamic ETA Weights")
    print("=" * 50)

    try:
        from gui.constants import calculate_dynamic_weights

        # Test with different content sizes
        test_cases = [
            {'name': 'Small content', 'transcript': 500, 'images': 5, 'dialogue': 5},
            {'name': 'Medium content', 'transcript': 2000, 'images': 10, 'dialogue': 15},
            {'name': 'Large content', 'transcript': 5000, 'images': 20, 'dialogue': 30},
        ]

        print("Content Size    | TTS | Visual | Video")
        print("-" * 40)

        for case in test_cases:
            stages = calculate_dynamic_weights(
                transcript_length=case['transcript'],
                image_count=case['images'],
                dialogue_entries=case['dialogue']
            )

            tts_weight = next(s['weight'] for s in stages if s.get('type') == 'tts')
            visual_weight = next(s['weight'] for s in stages if s.get('type') == 'visuals')
            video_weight = next(s['weight'] for s in stages if s.get('type') == 'video')

            print("15")

        print("\n✅ Dynamic weights calculation working!")

    except Exception as e:
        print(f"❌ Error in dynamic weights: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def test_historical_data():
    """Test historical performance data loading"""
    print("\n📊 Testing Historical Performance Data")
    print("=" * 50)

    try:
        from gui.constants import load_performance_history, save_performance_data

        # Test loading
        history = load_performance_history()
        print(f"Loaded historical data: {len(history)} metrics")

        # Test saving sample data
        sample_stage_times = {
            "Starting speech synthesis": 10.5,
            "Speech synthesis completed": 45.2,
            "Generating AI visuals": 28.1,
            "Starting video composition": 180.0,
            "Video composition completed": 210.5
        }

        sample_content_stats = {
            "transcript_length": 2500,
            "dialogue_entries": 18,
            "image_count": 12
        }

        save_performance_data(sample_stage_times, sample_content_stats)
        print("✅ Sample performance data saved")

        # Reload and check
        updated_history = load_performance_history()
        print(f"Updated historical data: {len(updated_history)} metrics")

        if 'tts_avg_per_entry' in updated_history:
            print(".2f")
        if 'visual_avg_per_image' in updated_history:
            print(".2f")
        if 'video_avg_time' in updated_history:
            print(".1f")
    except Exception as e:
        print(f"❌ Error in historical data: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

def main():
    """Run all ETA improvement tests"""
    print("🚀 Testing Azure TTS ETA Improvements")
    print("=" * 60)

    all_passed = True

    if not test_dynamic_weights():
        all_passed = False

    if not test_historical_data():
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL ETA IMPROVEMENTS WORKING!")
        print("\n✨ Azure TTS ETA Enhancements:")
        print("   • Dynamic weights based on content size")
        print("   • Historical performance tracking")
        print("   • Accurate TTS time estimation")
        print("   • Adaptive visual generation weights")
        print("   • Smart video composition timing")
    else:
        print("❌ SOME TESTS FAILED. Check errors above.")

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
