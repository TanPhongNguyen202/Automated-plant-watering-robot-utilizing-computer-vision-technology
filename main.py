"""
Robot Main Control Module
Handles mode switching and menu interface for the automated plant-watering robot.
"""

from src.robot.modes import Modes
from src.utils.logger import Logger
from time import sleep

# Constants (Kept exactly as previous versions)
MENU_SLEEP_TIME = 1
VALID_OPTIONS = {'1', '2', '3'}
OPTION_MANUAL = '1'
OPTION_AUTO = '2'
OPTION_QUIT = '3'
MODE_MANUAL = 'manual'
MODE_AUTO = 'automatic'


def display_menu() -> None:
    """Display the main control menu to the user."""
    print("\n" + "=" * 40)
    print("ROBOT CONTROL MENU")
    print("=" * 40)
    print("1. Switch to Manual Mode")
    print("2. Switch to Automatic Mode")
    print("3. Quit")
    print("=" * 40)


def handle_mode_switch(modes: Modes, logger: Logger, new_mode: str, 
                       current_mode: str) -> str:
    """
    Handle mode switching logic.
    
    Args:
        modes: The Modes object
        logger: The Logger object
        new_mode: The new mode to switch to
        current_mode: The current mode
    
    Returns:
        The new current mode or the previous one if already in that mode
    """
    if current_mode != new_mode:
        modes.switch_mode(new_mode)
        logger.log_info(f"Switched to {new_mode} mode.")
        
        if new_mode == MODE_MANUAL:
            modes.manual_control()
        elif new_mode == MODE_AUTO:
            modes.automatic_mode()
        
        return new_mode
    else:
        print(f"Already in {new_mode} mode.")
        return current_mode


def main() -> None:
    """Main application entry point."""
    logger = Logger()
    logger.log_info("Robot system starting...")
    
    # FIX #4: Only ONE instance of Modes handles everything. 
    # No standalone Motors() to prevent Raspberry Pi GPIO Pin multiplexing conflicts.
    modes = Modes()
    current_mode = None

    try:
        while True:
            display_menu()
            user_input = input("Choose an option (1/2/3): ").strip()

            if user_input not in VALID_OPTIONS:
                print("Invalid input! Please enter 1, 2, or 3.")
                continue

            if user_input == OPTION_MANUAL:
                current_mode = handle_mode_switch(modes, logger, MODE_MANUAL, 
                                                   current_mode)
            elif user_input == OPTION_AUTO:
                current_mode = handle_mode_switch(modes, logger, MODE_AUTO, 
                                                   current_mode)
            elif user_input == OPTION_QUIT:
                logger.log_info("Shutting down robot system...")
                break

            sleep(MENU_SLEEP_TIME)

    except KeyboardInterrupt:
        logger.log_info("Robot system interrupted by user (Ctrl+C).")
    except Exception as e:
        logger.log_error(f"An error occurred: {e}")
    finally:
        # Ironclad Cleanup: Stop motors and release resources safely
        logger.log_info("Executing system cleanup...")
        try:
            # Check for explicit cleanup method (preferred - releases camera/GPIOs)
            if hasattr(modes, 'cleanup') and callable(modes.cleanup):
                modes.cleanup()
                logger.log_info("Robot cleanup completed successfully.")
            # Fallback: stop motors directly via internal modes attribute
            elif hasattr(modes, 'motors') and modes.motors is not None:
                if hasattr(modes.motors, 'stop_all') and callable(modes.motors.stop_all):
                    modes.motors.stop_all()
                    logger.log_info("Motors stopped via fallback mechanism.")
            else:
                logger.log_warning("No explicit cleanup or motor control methods found in Modes.")
        except Exception as cleanup_error:
            logger.log_error(f"Critical error during hardware cleanup: {cleanup_error}")
        
        logger.log_info("Robot system stopped.")


if __name__ == "__main__":
    main()