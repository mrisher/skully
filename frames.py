import maestro
import time
from scipy.interpolate import interp1d
import json

# Define tweening curves
def linear(t):
    return t

def ease_in_out_quad(t):
    if t < 0.5:
        return 2 * t * t
    else:
        return -2 * t * t + 4 * t - 1

def ease_in_out_cubic(t):
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 4 * t * t * t - 12 * t * t + 12 * t - 3


def animate_servos(servo_controller, keyframes, servo_config, tween_func=linear):
    """
    Animates servos based on keyframes and a tweening function.

    Args:
        servo_controller: An instance of the maestro.Controller.
        keyframes: A dictionary where keys are servo channels (str) and values are lists of [time, position] keyframes.
        servo_config: A dictionary with servo channel configurations.
        tween_func: A function to apply for tweening (e.g., linear, ease_in_out).
    """
    interpolators = {}
    all_times = []

    for channel_str, track in keyframes.items():
        channel = int(channel_str)
        if channel not in servo_config:
            print(f"Warning: Servo {channel} not defined in config.json. Skipping.")
            continue
        times = [kf[0] for kf in track]
        positions = [kf[1] for kf in track]
        all_times.extend(times)
        # Hold the last position when animating past the last keyframe
        interpolators[channel] = interp1d(times, positions, kind='linear', bounds_error=False, fill_value=(positions[0], positions[-1]))

    start_time = time.time()
    total_duration = max(all_times) if all_times else 0
    
    update_interval = 0.01  # 100 Hz update rate

    unique_keyframe_times = sorted(list(set(all_times)))
    next_keyframe_idx = 0

    while True:
        loop_start_time = time.time()
        elapsed_time = loop_start_time - start_time

        if elapsed_time > total_duration:
            break

        # Print a message when we pass a keyframe time
        if next_keyframe_idx < len(unique_keyframe_times) and elapsed_time >= unique_keyframe_times[next_keyframe_idx]:
            print(f"Keyframe at t={unique_keyframe_times[next_keyframe_idx]:.2f}s")
            next_keyframe_idx += 1

        # Apply the tweening function to the overall timeline
        progress = elapsed_time / total_duration if total_duration > 0 else 0
        tweened_progress = tween_func(progress)
        tweened_time = tweened_progress * total_duration

        for channel, interpolator in interpolators.items():
            # Calculate the current target value based on the interpolated time
            normalized_target = interpolator(tweened_time)

            # Map the normalized value to the servo's pulse width
            min_us, max_us = servo_config[channel]
            pulse_us = int(min_us + (max_us - min_us) * normalized_target)

            # Convert microseconds to maestro's internal units (quarter microseconds)
            maestro_target = pulse_us * 4
            servo_controller.setTarget(channel, maestro_target)

        # Calculate time to sleep to maintain frame rate
        processing_time = time.time() - loop_start_time
        sleep_time = update_interval - processing_time
        if sleep_time > 0:
            time.sleep(sleep_time)

    # Ensure servos are at their final position
    for channel, interpolator in interpolators.items():
        # Get position at the very end of the animation
        final_position = interpolator(total_duration)
        min_us, max_us = servo_config[channel]
        pulse_us = int(min_us + (max_us - min_us) * final_position)
        maestro_target = pulse_us * 4
        servo_controller.setTarget(channel, maestro_target)
        print(f"Final servo {channel} target: {maestro_target}")

if __name__ == '__main__':
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    port = config.get('port', '/dev/tty.usbmodem004821521') # Default port
    servo_config_str_keys = config.get('servos', {})
    servo_config = {int(k): v for k, v in servo_config_str_keys.items()}

    # Load keyframes
    with open('keyframes.json', 'r') as f:
        keyframes = json.load(f)

    # Connect to the Maestro controller
    try:
        servo = maestro.Controller(port)
        print("Connected to Maestro controller.")

        # Set servo speeds and accelerations for smoother movement
        servo.setAccel(0, 4)
        servo.setSpeed(0, 10)
        servo.setAccel(1, 4)
        servo.setSpeed(1, 10)

        # Animate with ease-in-out curve
        print("Starting animation with ease-in-out curve...")
        animate_servos(servo, keyframes, servo_config, tween_func=ease_in_out_quad)
        print("Animation complete.")

    except Exception as e:
        print(f"Error: {e}")
        print("Check if the Maestro controller is connected and the port is correct.")
    finally:
        if 'servo' in locals():
            servo.close()
            print("Servo controller closed.")