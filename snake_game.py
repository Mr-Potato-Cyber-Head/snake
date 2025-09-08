from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QCheckBox, QLabel, QHBoxLayout, QGridLayout, QTextEdit
from PyQt5.QtGui import QPainter, QColor, QFont, QImage, QTransform, QMovie, QPainterPath, QRegion, QPixmap, QPalette, QBrush
from PyQt5.QtCore import Qt, QTimer, QUrl, QRect, QSize
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import sys
import random
import os
import json

class SnakeGame(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Snake")
        
        # Get screen size
        screen = QApplication.primaryScreen().size()
        self.screen_width = screen.width()
        self.screen_height = screen.height()

        # Track mouse position for dragging
        self.old_pos = None
        
        # Initialize high_score before calling setup_data_directory
        self.high_score = 0
        
        # Setup data directory and high score first
        self.setup_data_directory()
        self.high_score = self.load_high_score()
        
        # Game grid size - adjust based on screen size
        self.cell_size = 35  # Cell size
        self.width = self.screen_width // self.cell_size  # Grid width fills screen
        self.height = self.screen_height // self.cell_size  # Grid height fills screen
        
        # Set window flags to ensure proper fullscreen
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        
        # Don't set border radius - it interferes with fullscreen
        self.border_radius = 0
        
        # Sound effects setting
        self.sound_enabled = True
        
        # Obstacles setting
        self.obstacles_enabled = True
        self.boulder_count = 9  # Default to 9 boulders
        
        # Initialize audio player
        self.sound_player = QMediaPlayer()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sound_effect_dir = os.path.join(current_dir, 'asset', 'sound_effect')
        self.apple_sound = QMediaContent(QUrl.fromLocalFile(os.path.join(sound_effect_dir, 'game_score.mp3')))
        self.golden_apple_sound = QMediaContent(QUrl.fromLocalFile(os.path.join(sound_effect_dir, 'golden_apple.mp3')))
        self.hover_sound = QMediaContent(QUrl.fromLocalFile(os.path.join(sound_effect_dir, 'hover_effect.wav')))
        
        # Set audio volume to a lower level
        self.sound_player.setVolume(30)  # 30% of maximum volume
        
        # Timer for cutting sound effects short
        self.sound_timer = QTimer()
        self.sound_timer.setSingleShot(True)
        self.sound_timer.timeout.connect(self.stop_sound)
        
        # More aggressive preloading with multiple attempts
        self.sound_player.setMedia(self.apple_sound)
        self.sound_player.setVolume(0)  # Silent during preload
        self.sound_player.play()
        
        # Create a timer to check if audio system is ready
        self.preload_attempts = 0
        self.preload_timer = QTimer()
        self.preload_timer.timeout.connect(self._check_audio_ready)
        self.preload_timer.start(10)  # Check every 10ms
        
        # Main menu state
        self.in_main_menu = True
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = False
        self.in_mission_intro = False  # New flag for mission intro screen
        
        # Campaign progress (which levels are unlocked)
        self.unlocked_levels = 1  # Only first level unlocked initially
        self.current_level = 0    # Current campaign level (0 means not in campaign mode)
        
        # Create a container widget that will hold all our screens
        self.container = QWidget()
        self.setCentralWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        
        # Setup menus (they'll be added to container when needed)
        self.setup_main_menu()
        self.setup_settings_menu()
        self.setup_game_mode_menu()
        self.setup_campaign_menu()  # Setup campaign level selection menu
        
        # Show the main menu initially
        self.container_layout.addWidget(self.menu_widget)
        
        # Colors
        self.bg_color = QColor(0, 51, 0)      # Dark green background
        self.grid_color = QColor(0, 45, 0)    # Slightly lighter green for grid
        self.snake_color = QColor(0, 255, 0)  # Bright green for snake
        
        # Initialize game state
        self.snake = [(self.width//2, self.height//2)]
        self.direction = (1, 0)
        self.score = 0
        self.game_over = False
        
        # Golden apple settings
        self.golden_apple_active = False
        self.apples_eaten = 0
        self.golden_apple_glow = True
        self.golden_apple_timer_value = 5
        self.golden_apple_current_time = self.golden_apple_timer_value
        self.golden_apple_spawned_in_current_basket = False  # Track if golden apple spawned in current basket
        
        # Load images
        asset_dir = os.path.join(current_dir, 'asset')
        self.images = {
            'apple': QImage(os.path.join(asset_dir, 'apple.png')),
            'apple_gold_glow': QImage(os.path.join(asset_dir, 'apple_gold_glow.png')),
            'apple_gold_glow_out': QImage(os.path.join(asset_dir, 'apple_gold_glow_out.png')),
            'body': QImage(os.path.join(asset_dir, 'snake_body.png')),
            'head': QImage(os.path.join(asset_dir, 'snake_head.png'))
        }
        
        # Load mission assets
        mission_dir = os.path.join(asset_dir, 'mission', 'mission 1')
        self.mission_images = {
            'green_crystal': QImage(os.path.join(mission_dir, 'green_crystal.png')),
            'red_crystal': QImage(os.path.join(mission_dir, 'red_crystal.png')),
        }
        
        # Load boulder images
        boulder_dir = os.path.join(asset_dir, 'boulder')
        self.boulder_images = []
        for i in range(1, 10):  # boulder1 through boulder9
            image = QImage(os.path.join(boulder_dir, f'boulder{i}.png'))
            if not image.isNull():
                self.boulder_images.append(image)
        
        # Initialize obstacles lists
        self.boulders = []
        
        # Load celebration GIF
        self.celebration_movie = QMovie(os.path.join(asset_dir, 'celebration.gif'))
        self.celebration_movie.setCacheMode(QMovie.CacheAll)
        self.celebration_movie.frameChanged.connect(self.update)  # Update screen when animation frame changes
        
        # Scale images
        for key in self.images:
            if not self.images[key].isNull():
                # After modification: Use nearest-neighbor (fast) transformation for pixelated scaling
                self.images[key] = self.images[key].scaled(self.cell_size, self.cell_size,
                                                            Qt.KeepAspectRatio, Qt.FastTransformation)
        
        # Scale mission images too
        for key in self.mission_images:
            if not self.mission_images[key].isNull():
                self.mission_images[key] = self.mission_images[key].scaled(
                    self.cell_size, self.cell_size,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
        
        # Initialize crystal tracking
        self.red_crystal_positions = []  # Will be filled in initialize_mission
        self.red_crystals_eaten = set()
        self.crystals_collected = 0
        self.slow_effect_active = False
        self.crystal_milestones = [0, 2, 5, 10, 15]  # After these green crystals, spawn red crystals
        
        # Create food (green crystal)
        self.food = self.create_food()
        
        # Immediately spawn two red crystals at game start
        self.initialize_red_crystals()
        
        # Setup timers
        self.golden_apple_timer = QTimer()
        self.golden_apple_timer.timeout.connect(self.golden_apple_countdown)
        self.golden_apple_timer.setInterval(1000)  # 1 second intervals
        
        self.golden_apple_blink_timer = QTimer()
        self.golden_apple_blink_timer.timeout.connect(self.toggle_golden_apple_glow)
        self.golden_apple_blink_timer.start(100)  # Blink every 200ms
        
        # Game timer - initially stopped until game starts
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        # Don't start the timer until game starts
        
        # Animation settings
        self.score_animation = 0
        self.score_animation_timer = QTimer()
        self.score_animation_timer.timeout.connect(self.update_score_animation)
        self.score_animation_timer.setInterval(50)  # 50ms for smooth animation
        
        self.new_high_score = False
        self.high_score_blink = False
        self.high_score_blink_timer = QTimer()
        self.high_score_blink_timer.timeout.connect(self.toggle_high_score_blink)
        self.high_score_blink_timer.setInterval(500)  # 500ms blink interval
        
        # Pause menu state
        self.paused = False
        self.pause_overlay = None
        self.setup_pause_overlay()
        
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Create mission timer
        self.mission_timer = QTimer(self)
        self.mission_timer.timeout.connect(self.update_oxygen_level)
        self.oxygen_level = 100  # Start with 100% oxygen
        self.oxygen_depletion_time = 90  # 90 seconds to fully deplete
        
        # Show fullscreen using a more direct approach
        self.showFullScreen()
        self.setFixedSize(self.screen_width, self.screen_height)
        
        # Make sure the window is truly maximized and takes up the entire screen
        self.move(0, 0)
        
        # In the constructor after creating the container widget:
        self.container.setFixedSize(self.screen_width, self.screen_height)
        
        # Load oxygen warning sound
        self.oxygen_warning_sound = QMediaContent(QUrl.fromLocalFile(os.path.join(sound_effect_dir, 'oxygen.mp3')))
        
        # Add oxygen warning timer and flag
        self.oxygen_warning_active = False
        self.oxygen_warning_timer = QTimer()
        self.oxygen_warning_timer.timeout.connect(self.play_oxygen_warning)
        self.oxygen_warning_timer.setInterval(5000)  # Play every 5 seconds

    def setup_data_directory(self):
        """Create data directory if it doesn't exist"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, 'data_score')
        self.score_file = os.path.join(self.data_dir, 'high_score.json')
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # Create JSON file with correct structure if it doesn't exist
        if not os.path.exists(self.score_file):
            default_data = {'scores': [], 'high_score': 0}
            with open(self.score_file, 'w') as f:
                json.dump(default_data, f)

    def load_high_score(self):
        """Load high score from JSON file"""
        try:
            if os.path.exists(self.score_file):
                with open(self.score_file, 'r') as f:
                    data = json.load(f)
                    return data.get('high_score', 0)
            else:
                return 0
        except Exception as e:
            return 0

    def save_high_score(self):
        """Save high score and current score to JSON file"""
        try:
            # Create default data structure
            default_data = {'scores': [], 'high_score': self.high_score}
            
            # Load existing data if file exists
            if os.path.exists(self.score_file):
                try:
                    with open(self.score_file, 'r') as f:
                        file_content = f.read().strip()
                        # Check if file is not empty
                        if file_content:
                            data = json.loads(file_content)
                            # Ensure both keys exist
                            if 'scores' not in data:
                                data['scores'] = []
                            if 'high_score' not in data:
                                data['high_score'] = 0
                        else:
                            data = default_data
                except Exception:
                    data = default_data
            else:
                data = default_data
                
            # Add current score to scores list
            if self.score > 0:  # Only add scores greater than 0
                data['scores'].append(self.score)
            
            # Keep only the last 10 scores
            if len(data['scores']) > 10:
                data['scores'] = data['scores'][-10:]
            
            # Update high score based on maximum score
            all_scores = data['scores'] + [data['high_score']]
            all_scores = [s for s in all_scores if s > 0]  # Remove zeros
            if all_scores:
                data['high_score'] = max(all_scores)
            
            # Make sure high score is at least the current high score
            if self.high_score > data['high_score']:
                data['high_score'] = self.high_score
            
            # Save updated data
            with open(self.score_file, 'w') as f:
                json.dump(data, f)
            
        except Exception:
            # If all else fails, create a new file with basic structure
            try:
                with open(self.score_file, 'w') as f:
                    json.dump({'scores': [self.score], 'high_score': self.high_score}, f)
            except:
                pass

    def update_high_score(self):
        """Update high score if current score is higher"""
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()

    def create_food(self):
        # Check for golden apple spawn
        if self.apples_eaten % 10 == 0:
            self.golden_apple_spawned_in_current_basket = False
        
        # Skip golden apple logic in mission mode
        if not hasattr(self, 'in_mission_mode') or not self.in_mission_mode:
            if (not self.golden_apple_active and 
                not self.golden_apple_spawned_in_current_basket and 
                self.apples_eaten > 0 and 
                random.random() < 0.1):
                
                self.golden_apple_active = True
                self.golden_apple_spawned_in_current_basket = True
                self.golden_apple_current_time = self.golden_apple_timer_value
                self.golden_apple_timer.start()
        
        # Create new food position with vertical restriction
        margin_top = 2  # Keep 2 cells from the top for score display
        
        # Create a list of all available positions
        available_positions = []
        for x in range(self.width):
            for y in range(margin_top, self.height):
                pos = (x, y)
                # Check if position is valid (not on snake or boulders)
                if pos not in self.snake and not any(pos in boulder_cells for boulder_cells, _ in self.boulders):
                    available_positions.append(pos)
        
        if not available_positions:
            # If no positions available, return a random position
            return (random.randint(0, self.width - 1), random.randint(margin_top, self.height - 1))
        
        # Select food position from available positions
        food_pos = random.choice(available_positions)
        
        # Place boulders only in casual mode
        if not hasattr(self, 'in_mission_mode') or not self.in_mission_mode:
            if self.obstacles_enabled and len(self.boulders) < self.boulder_count:
                self.place_boulders(food_pos)
        
        return food_pos

    def place_boulders(self, food_pos):
        """Place boulder obstacles"""
        # Skip if obstacles are disabled or we're at max boulders
        if not self.obstacles_enabled or len(self.boulders) >= self.boulder_count:
            return
        
        # Find positions where the snake will be in the next few moves
        immediate_path = []
        if len(self.snake) > 0:
            head = self.snake[0]
            next_pos = ((head[0] + self.direction[0]) % self.width, 
                        (head[1] + self.direction[1]) % self.height)
            immediate_path.append(next_pos)
        
        margin_top = 2  # Same margin as for food
        
        # Place boulders (2x2)
        attempts = 0
        while len(self.boulders) < self.boulder_count and attempts < 100:
            attempts += 1
            
            # Get a random position for the top-left corner of the boulder
            x = random.randint(0, self.width - 2)  # -2 to leave room for width of boulder
            y = random.randint(margin_top, self.height - 2)  # -2 to leave room for height of boulder
            
            # Generate the four positions for the 2x2 boulder
            boulder_positions = [
                (x, y),        # Top-left
                (x + 1, y),    # Top-right
                (x, y + 1),    # Bottom-left
                (x + 1, y + 1) # Bottom-right
            ]
            
            # Check if this boulder would overlap with anything
            overlap = False
            for pos in boulder_positions:
                if (pos in self.snake or 
                    pos == food_pos or 
                    pos in immediate_path or
                    any(pos in existing_boulder for existing_boulder, _ in self.boulders)):
                    overlap = True
                    break
            
            # If no overlap and we have boulder images, add the boulder
            if not overlap and self.boulder_images:
                self.boulders.append((boulder_positions, random.choice(self.boulder_images)))

    def setup_main_menu(self):
        """Setup the main menu UI"""
        # Create a widget for the menu (don't set as central)
        self.menu_widget = QWidget()
        
        # Create a layout for the menu
        layout = QVBoxLayout()
        
        # Add spacer at the top to push buttons down
        layout.addStretch()
        
        # Common button style - removed borders
        button_style = """
            QPushButton {
                background-color: #005500;
                color: #00FF00;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #007700;
            }
            QPushButton:pressed {
                background-color: #009900;
            }
        """
        
        # Create and add the buttons with hover sound
        self.play_button = HoverButton("Play", self, self.sound_player, lambda: self.sound_enabled)
        self.play_button.set_hover_sound(self.hover_sound)
        self.play_button.setFixedSize(200, 50)
        self.play_button.setFont(QFont("Courier", 16))
        self.play_button.setStyleSheet(button_style)
        self.play_button.clicked.connect(self.start_game)
        layout.addWidget(self.play_button, 0, Qt.AlignHCenter)
        
        # Add spacing between buttons
        layout.addSpacing(20)
        
        # Create Settings button
        self.settings_button = HoverButton("Settings", self, self.sound_player, lambda: self.sound_enabled)
        self.settings_button.set_hover_sound(self.hover_sound)
        self.settings_button.setFixedSize(200, 50)
        self.settings_button.setFont(QFont("Courier", 16))
        self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_button, 0, Qt.AlignHCenter)
        
        # Add spacing between buttons
        layout.addSpacing(20)
        
        # Create Exit button
        self.exit_button = HoverButton("Exit", self, self.sound_player, lambda: self.sound_enabled)
        self.exit_button.set_hover_sound(self.hover_sound)
        self.exit_button.setFixedSize(200, 50)
        self.exit_button.setFont(QFont("Courier", 16))
        self.exit_button.setStyleSheet(button_style)
        self.exit_button.clicked.connect(self.close)
        layout.addWidget(self.exit_button, 0, Qt.AlignHCenter)
        
        # Add spacer at the bottom
        layout.addStretch()
        
        # Set the layout
        self.menu_widget.setLayout(layout)

    def setup_settings_menu(self):
        """Setup the settings menu"""
        # Create a widget for the settings (don't set as central)
        self.settings_widget = QWidget()
        
        # Create a layout for the settings
        layout = QVBoxLayout()
        
        # Add spacer at the top
        layout.addStretch()
        
        # Add a title
        title_label = QLabel("Settings", self)
        title_label.setFont(QFont("Courier", 24, QFont.Bold))
        title_label.setStyleSheet("color: #00FF00;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(40)
        
        # Create horizontal layout for sound effects setting
        sound_layout = QHBoxLayout()
        
        # Sound effects label
        sound_label = QLabel("Sound Effects", self)
        sound_label.setFont(QFont("Courier", 16))
        sound_label.setStyleSheet("color: #00FF00;")
        sound_layout.addWidget(sound_label)
        
        sound_layout.addStretch()  # Push the labels apart
        
        # Create On/Off labels
        self.sound_on_label = QLabel("On", self)
        self.sound_on_label.setFont(QFont("Courier", 16))
        self.sound_on_label.setStyleSheet("color: #00FF00; text-decoration: underline;")
        
        self.sound_off_label = QLabel("Off", self)
        self.sound_off_label.setFont(QFont("Courier", 16))
        self.sound_off_label.setStyleSheet("color: #00FF00;")
        
        # Add labels to layout
        sound_layout.addWidget(self.sound_on_label)
        sound_layout.addWidget(self.sound_off_label)
        
        # Add sound layout to main layout
        layout.addLayout(sound_layout)
        
        layout.addSpacing(20)  # Add spacing between settings
        
        # Create horizontal layout for boulders setting
        obstacles_layout = QHBoxLayout()
        
        # Boulders label
        obstacles_label = QLabel("Boulders", self)
        obstacles_label.setFont(QFont("Courier", 16))
        obstacles_label.setStyleSheet("color: #00FF00;")
        obstacles_layout.addWidget(obstacles_label)
        
        obstacles_layout.addStretch()  # Push the labels apart
        
        # Create multiple options for boulder count
        self.boulder_off_label = QLabel("Off", self)
        self.boulder_off_label.setFont(QFont("Courier", 16))
        self.boulder_off_label.setStyleSheet("color: #00FF00;")
        
        self.boulder_3_label = QLabel("3", self)
        self.boulder_3_label.setFont(QFont("Courier", 16))
        self.boulder_3_label.setStyleSheet("color: #00FF00;")
        
        self.boulder_6_label = QLabel("6", self)
        self.boulder_6_label.setFont(QFont("Courier", 16))
        self.boulder_6_label.setStyleSheet("color: #00FF00;")
        
        self.boulder_9_label = QLabel("9", self)
        self.boulder_9_label.setFont(QFont("Courier", 16))
        self.boulder_9_label.setStyleSheet("color: #00FF00;")
        
        # Add labels to layout
        obstacles_layout.addWidget(self.boulder_off_label)
        obstacles_layout.addWidget(self.boulder_3_label)
        obstacles_layout.addWidget(self.boulder_6_label)
        obstacles_layout.addWidget(self.boulder_9_label)
        
        # Add obstacles layout to main layout
        layout.addLayout(obstacles_layout)
        
        layout.addSpacing(40)  # More space before Back button
        
        # Back button with hover sound
        back_button = HoverButton("Back", self, self.sound_player, lambda: self.sound_enabled)
        back_button.set_hover_sound(self.hover_sound)
        back_button.setFixedSize(200, 50)
        back_button.setFont(QFont("Courier", 16))
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #005500;
                color: #00FF00;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #007700;
            }
            QPushButton:pressed {
                background-color: #009900;
            }
        """)
        back_button.clicked.connect(self.show_main_menu)
        layout.addWidget(back_button, 0, Qt.AlignHCenter)
        
        # Add spacer at the bottom
        layout.addStretch()
        
        # Set the layout
        self.settings_widget.setLayout(layout)
        
        # Make labels clickable
        self.sound_on_label.mousePressEvent = self.toggle_sound_on
        self.sound_off_label.mousePressEvent = self.toggle_sound_off
        
        # Make boulder count options clickable
        self.boulder_off_label.mousePressEvent = lambda event: self.set_boulder_count(0)
        self.boulder_3_label.mousePressEvent = lambda event: self.set_boulder_count(3)
        self.boulder_6_label.mousePressEvent = lambda event: self.set_boulder_count(6)
        self.boulder_9_label.mousePressEvent = lambda event: self.set_boulder_count(9)
        
        # Update the labels based on current settings
        self.update_sound_labels()
        self.update_boulder_labels()

    def toggle_sound_on(self, event):
        """Enable sound effects"""
        self.sound_enabled = True
        self.update_sound_labels()

    def toggle_sound_off(self, event):
        """Disable sound effects"""
        self.sound_enabled = False
        self.update_sound_labels()

    def update_sound_labels(self):
        """Update the appearance of sound labels based on current state"""
        if self.sound_enabled:
            # Make ON more visible when selected
            self.sound_on_label.setStyleSheet("""
                color: #00FF00; 
                font-weight: bold;
                background-color: #004400;
                padding: 5px;
                border-radius: 5px;
            """)
            self.sound_off_label.setStyleSheet("color: #00FF00;")
        else:
            self.sound_on_label.setStyleSheet("color: #00FF00;")
            # Make OFF more visible when selected
            self.sound_off_label.setStyleSheet("""
                color: #00FF00; 
                font-weight: bold;
                background-color: #004400;
                padding: 5px;
                border-radius: 5px;
            """)

    def set_boulder_count(self, count):
        """Set the number of boulders"""
        self.boulder_count = count
        self.obstacles_enabled = (count > 0)
        self.update_boulder_labels()

    def update_boulder_labels(self):
        """Update the appearance of boulder count labels based on current state"""
        # Reset all to default style
        default_style = "color: #00FF00;"
        selected_style = """
            color: #00FF00; 
            font-weight: bold;
            background-color: #004400;
            padding: 5px;
            border-radius: 5px;
        """
        
        self.boulder_off_label.setStyleSheet(default_style)
        self.boulder_3_label.setStyleSheet(default_style)
        self.boulder_6_label.setStyleSheet(default_style)
        self.boulder_9_label.setStyleSheet(default_style)
        
        # Highlight the selected option
        if not self.obstacles_enabled or self.boulder_count == 0:
            self.boulder_off_label.setStyleSheet(selected_style)
        elif self.boulder_count == 3:
            self.boulder_3_label.setStyleSheet(selected_style)
        elif self.boulder_count == 6:
            self.boulder_6_label.setStyleSheet(selected_style)
        elif self.boulder_count == 9:
            self.boulder_9_label.setStyleSheet(selected_style)

    def show_main_menu(self):
        """Show the main menu"""
        # Hide pause overlay
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            self.pause_overlay.setVisible(False)
        
        # Unpause the game
        self.paused = False
        
        # Stop the celebration if showing
        if hasattr(self, 'celebration_movie') and self.celebration_movie.state() == QMovie.Running:
            self.celebration_movie.stop()
        
        # Restore original colors if needed
        if hasattr(self, 'original_bg_color') and hasattr(self, 'in_mission_mode') and self.in_mission_mode:
            self.bg_color = self.original_bg_color
            self.grid_color = self.original_grid_color
        
        # Clear container layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
            
        # Add and show main menu
        self.container_layout.addWidget(self.menu_widget)
        self.menu_widget.show()
        
        # Reset game state
        self.game_over = False
        self.in_main_menu = True
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = False
        
        # Reset mission state
        self.in_mission_mode = False
        self.in_mission_intro = False
        
        # Make sure mission timer is stopped
        if hasattr(self, 'mission_timer') and self.mission_timer.isActive():
            self.mission_timer.stop()
        
        self.update()

    def show_settings(self):
        """Show the settings menu"""
        # Hide pause overlay
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            self.pause_overlay.setVisible(False)
        
        # Clear container layout
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
        
        # Add and show settings
        self.container_layout.addWidget(self.settings_widget)
        self.settings_widget.show()
        self.in_settings = True
        self.in_main_menu = False
        self.update()

    def toggle_sound(self, state):
        """Toggle sound effects on/off"""
        self.sound_enabled = (state == Qt.Checked)

    def start_game(self):
        """Show the game mode selection menu instead of starting game directly"""
        self.show_game_mode_menu()

    def show_game_mode_menu(self):
        """Show the game mode selection menu"""
        # Stop any running game timers
        if self.timer.isActive():
            self.timer.stop()
        
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Add and show the game mode menu
        self.container_layout.addWidget(self.game_mode_widget)
        self.game_mode_widget.show()
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = True
        self.in_campaign_menu = False
        self.in_mission_intro = False
        
        # Make sure game is paused
        self.paused = True

    def start_casual_game(self):
        """Start a casual (normal) game"""
        # Hide pause overlay
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            self.pause_overlay.setVisible(False)
        
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Reset game state
        self.reset_game()
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        
        # Start the game timer
        self.paused = False
        self.timer.start(100)  # Adjust speed as needed
        
        # Set focus to the game
        self.setFocus()

    def start_campaign_game(self):
        """Open campaign menu showing all levels as coming soon"""
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Add and show the campaign menu
        self.container_layout.addWidget(self.campaign_widget)
        self.campaign_widget.show()
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = True
        
        # Make sure game is paused
        self.paused = True
        self.timer.stop()

    def start_campaign_level(self, level):
        """Start a campaign level"""
        if level > self.unlocked_levels:
            return  # Level is locked
        
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Reset game state
        self.reset_game()
        
        # Set the current level
        self.current_level = level
        
        # Configure game based on level (customize difficulty per level)
        self.configure_level(level)
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = False
        
        # Start the game timer
        self.paused = False
        self.timer.start(100)  # Base speed, might be adjusted by level configuration
        
        # Set focus to the game
        self.setFocus()

    def configure_level(self, level):
        """Configure game settings based on level difficulty"""
        # Base settings
        self.obstacles_enabled = True
        
        # Configure difficulty based on level
        if level == 1:
            self.boulder_count = 2
            self.timer.setInterval(120)  # Slower speed for level 1
        elif level == 2:
            self.boulder_count = 3
            self.timer.setInterval(115)
        elif level == 3:
            self.boulder_count = 4
            self.timer.setInterval(110)
        elif level == 4:
            self.boulder_count = 5
            self.timer.setInterval(105)
        elif level == 5:
            self.boulder_count = 6
            self.timer.setInterval(100)
        elif level == 6:
            self.boulder_count = 7
            self.timer.setInterval(90)  # Fastest speed for level 6
        
        # Place boulders
        self.place_boulders(self.food)

    def apply_rounded_corners(self):
        """Apply rounded corners to the window - disabled in fullscreen mode"""
        # In fullscreen mode, don't apply any mask or rounded corners
        pass

    def paintEvent(self, event):
        """Draw the game elements"""
        qp = QPainter()
        qp.begin(self)
        
        # Scale drawing based on window size
        # Use size().width() and size().height() to get the *actual* window size
        playable_width = self.size().width()
        playable_height = self.size().height()
        
        # Calculate cell size based on the *actual* window dimensions
        cell_size_x = playable_width / self.width
        cell_size_y = playable_height / self.height
        
        # Fill the entire window with the background color first
        qp.fillRect(0, 0, playable_width, playable_height, self.bg_color)
        
        # If in main menu or settings, paint the menu background and return
        if self.in_main_menu or self.in_settings:
            # Only draw title if in main menu
            if self.in_main_menu and not self.in_settings:
                # Draw the game title
                qp.setPen(self.snake_color)
                qp.setFont(QFont('Courier', 36, QFont.Bold))
                title_text = "SNAKE GAME"
                metrics = qp.fontMetrics()
                text_width = metrics.width(title_text)
                # Convert x to an integer using round()
                x = round((playable_width - text_width) / 2)
                qp.drawText(x, 100, title_text)
            
            return
        
        # Regular game painting - now with antialiasing off for pixel-perfect game grid
        qp.setRenderHint(QPainter.Antialiasing, False)
        
        # Draw checkerboard pattern
        for i in range(self.width):
            for j in range(self.height):
                x = i * cell_size_x
                y = j * cell_size_y
                # Round x and y to the nearest integer *before* passing to fillRect
                x = round(x)
                y = round(y)
                # Use the calculated cell_size_x and cell_size_y, and round up the size
                # to ensure we cover any fractional parts of the screen
                if (i + j) % 2 == 0:
                    qp.fillRect(x, y, round(cell_size_x + 0.5), round(cell_size_y + 0.5), self.bg_color)
                else:
                    qp.fillRect(x, y, round(cell_size_x + 0.5), round(cell_size_y + 0.5), self.grid_color)
        
        # Display score and high score at the top of the game screen
        if not self.game_over:
            # Draw score text
            qp.setPen(self.snake_color)
            qp.setFont(QFont('Courier', 12))
            
            if hasattr(self, 'in_mission_mode') and self.in_mission_mode:
                # For mission mode, show remaining crystals and oxygen level
                crystals_remaining = self.crystals_required - self.crystals_collected
                score_text = f"GREEN CRYSTAL REMAINING: {crystals_remaining}"
                
                # Oxygen level display (rounded to integer)
                oxygen_text = f"OXYGEN LEVEL: {int(self.oxygen_level)}%"
                
                # Position for crystal count (left side)
                qp.drawText(10, 20, score_text)
                
                # Position for oxygen (right side)
                metrics = qp.fontMetrics()
                oxygen_width = metrics.width(oxygen_text)
                
                # Add a warning color when oxygen is low (less than 30%)
                if self.oxygen_level <= 30:
                    qp.setPen(QColor(255, 50, 50))  # Red for danger
                elif self.oxygen_level <= 50:
                    qp.setPen(QColor(255, 165, 0))  # Orange for warning
                qp.drawText(self.width * self.cell_size - oxygen_width - 10, 20, oxygen_text)
            else:
                # For normal mode, show regular score and high score
                score_text = f"SCORE: {self.score}"
                high_score_text = f"HIGH SCORE: {self.high_score}"
                
                # Position for score (left side)
                qp.drawText(10, 20, score_text)
                
                # Position for high score (right side)
                metrics = qp.fontMetrics()
                high_score_width = metrics.width(high_score_text)
                qp.drawText(self.width * self.cell_size - high_score_width - 10, 20, high_score_text)
        
        # Draw snake - using the calculated cell sizes for positioning
        for i, segment in enumerate(self.snake):
            # Calculate the position using the same cell_size_x and cell_size_y
            x = round(segment[0] * cell_size_x)
            y = round(segment[1] * cell_size_y)
            
            if i == 0:  # Head
                # Rotate head based on current direction
                rotated_head = self.get_rotated_image(self.images['head'], self.direction)
                qp.drawImage(x, y, rotated_head)
            else:  # Body
                qp.drawImage(x, y, self.images['body'])
        
        # Draw food (normal apple, golden apple, or mission crystal)
        if hasattr(self, 'in_mission_mode') and self.in_mission_mode:
            # Draw the appropriate crystal for mission mode
            x = round(self.food[0] * cell_size_x)
            y = round(self.food[1] * cell_size_y)
            
            # Use regular cell size for 1x1 crystal
            crystal_width = round(cell_size_x)
            crystal_height = round(cell_size_y)
            
            # Determine which crystal image to use
            crystal_type = 'green'
            if hasattr(self, 'current_crystal_type'):
                crystal_type = self.current_crystal_type
            
            # Draw the crystal image if it exists
            crystal_key = crystal_type + '_crystal'
            if crystal_key in self.mission_images and not self.mission_images[crystal_key].isNull():
                crystal_img = self.mission_images[crystal_key].scaled(
                    crystal_width, crystal_height,
                    Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                )
                qp.drawImage(x, y, crystal_img)
            
            # Draw red crystals
            if hasattr(self, 'red_crystal_positions'):
                for pos in self.red_crystal_positions:
                    x = round(pos[0] * cell_size_x)
                    y = round(pos[1] * cell_size_y)
                    
                    # Draw the red crystal image
                    if 'red_crystal' in self.mission_images and not self.mission_images['red_crystal'].isNull():
                        red_crystal_img = self.mission_images['red_crystal'].scaled(
                            crystal_width, crystal_height,
                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                        )
                        qp.drawImage(x, y, red_crystal_img)
        
        else:
            # Regular apple drawing
            if self.golden_apple_active:
                apple_img = self.images['apple_gold_glow' if self.golden_apple_glow else 'apple_gold_glow_out']
                
                # Draw countdown timer
                qp.setPen(self.snake_color)
                qp.setFont(QFont('Courier', 24))
                timer_text = str(self.golden_apple_current_time)
                metrics = qp.fontMetrics()
                text_width = metrics.width(timer_text)
                x = round((playable_width - text_width) / 2)
                y = 30  # Position at top of screen
                qp.drawText(x, y, timer_text)
            else:
                apple_img = self.images['apple']
            
            qp.drawImage(
                round(self.food[0] * cell_size_x),
                round(self.food[1] * cell_size_y),
                apple_img
            )
        
        # Draw boulders (2x2 size)
        for boulder_positions, boulder_img in self.boulders:
            # Calculate the top-left corner and size (2x2 cells)
            top_left_pos = boulder_positions[0]
            x = round(top_left_pos[0] * cell_size_x)
            y = round(top_left_pos[1] * cell_size_y)
            width = round(2 * cell_size_x)
            height = round(2 * cell_size_y)
            
            # Scale image to fill 2x2 cells
            scaled_img = boulder_img.scaled(width, height, Qt.KeepAspectRatio, Qt.FastTransformation)
            qp.drawImage(x, y, scaled_img)
        
        # Call our specialized red crystal drawing method AFTER drawing everything else
        # but before drawing UI overlays (game over, pause screens, etc.)
        if hasattr(self, 'red_crystal_positions'):
            self.draw_red_crystals(qp, cell_size_x, cell_size_y)
        
        # Game over screen
        if self.game_over:
            # Semi-transparent overlay
            overlay = QColor(0, 0, 0, 180)  # Dark overlay with 70% opacity
            
            # Create a QRect for the entire screen area
            screen_width = int(self.width * cell_size_x)
            screen_height = int(self.height * cell_size_y)
            screen_rect = QRect(0, 0, screen_width, screen_height)
            
            # Use QRect object directly
            qp.fillRect(screen_rect, overlay)
            
            # Draw game over text
            qp.setPen(QColor(0, 255, 0))  # Bright green
            qp.setFont(QFont('Courier', 36, QFont.Bold))
            
            # Check if game ended because of oxygen depletion in mission mode
            if hasattr(self, 'oxygen_level') and self.oxygen_level <= 0:
                # Special display for oxygen depletion in mission mode
                game_over_message = "OXYGEN DEPLETED"
                text_width = qp.fontMetrics().width(game_over_message)
                qp.drawText(int((screen_width - text_width) // 2), 
                           int(screen_height // 3), game_over_message)
                
                # Draw mission result instead of score
                qp.setFont(QFont('Courier', 24))
                crystals_text = f"CRYSTALS COLLECTED: {self.crystals_collected}"
                crystals_width = qp.fontMetrics().width(crystals_text)
                
                # Calculate vertical positions
                result_y = int(screen_height // 2)
                
                # Show only crystals collected for mission mode
                qp.drawText(int((screen_width - crystals_width) // 2), result_y, crystals_text)
                
                # Draw restart instruction
                qp.setPen(QColor(0, 255, 0))
                qp.setFont(QFont('Courier', 18))
                restart_text = "PRESS R TO RESTART MISSION"
                restart_width = qp.fontMetrics().width(restart_text)
                qp.drawText(int((screen_width - restart_width) // 2), 
                           result_y + 100, restart_text)
                
                # Draw ESC instruction
                esc_text = "ESC TO RETURN TO MENU"
                esc_width = qp.fontMetrics().width(esc_text)
                qp.drawText(int((screen_width - esc_width) // 2), 
                           result_y + 140, esc_text)
                
                # Show oxygen depleted message
                qp.setPen(QColor(0, 200, 255))  # Light blue for oxygen message
                qp.setFont(QFont('Courier', 16))
                oxygen_message = "You ran out of oxygen! Collect green crystals to replenish it."
                oxygen_width = qp.fontMetrics().width(oxygen_message)
                qp.drawText(int((screen_width - oxygen_width) // 2), 
                          result_y + 200, oxygen_message)
                
            else:
                # Regular game over display for normal game mode
                game_over_message = "GAME OVER"
                text_width = qp.fontMetrics().width(game_over_message)
                qp.drawText(int((screen_width - text_width) // 2), 
                           int(screen_height // 3), game_over_message)
                
                # Draw score
                qp.setFont(QFont('Courier', 24))
                score_text = f"SCORE: {self.score}"
                score_width = qp.fontMetrics().width(score_text)
                
                # Draw high score with potential blinking
                high_score_text = f"HIGH SCORE: {self.high_score}"
                high_score_width = qp.fontMetrics().width(high_score_text)
                
                # Calculate vertical positions
                score_y = int(screen_height // 2)
                
                # Draw scores with better spacing
                qp.drawText(int((screen_width - score_width) // 2), score_y, score_text)
                
                # Draw high score with blinking effect if it's a new high score
                if self.new_high_score and self.high_score_blink:
                    qp.setPen(QColor(255, 255, 0))  # Yellow for blinking
                else:
                    qp.setPen(QColor(0, 255, 0))  # Green otherwise
                    
                qp.drawText(int((screen_width - high_score_width) // 2), 
                           score_y + 40, high_score_text)
                
                # Draw restart instruction
                qp.setPen(QColor(0, 255, 0))
                qp.setFont(QFont('Courier', 18))
                restart_text = "PRESS R TO RESTART"
                restart_width = qp.fontMetrics().width(restart_text)
                qp.drawText(int((screen_width - restart_width) // 2), 
                           score_y + 100, restart_text)
                
                # Draw ESC instruction
                esc_text = "ESC TO RETURN TO MENU"
                esc_width = qp.fontMetrics().width(esc_text)
                qp.drawText(int((screen_width - esc_width) // 2), 
                           score_y + 140, esc_text)

        # If game is paused, draw semi-transparent overlay
        if self.paused:
            overlay = QColor(0, 0, 0, 128)  # Semi-transparent black
            qp.fillRect(0, 0, self.width * self.cell_size, 
                            self.height * self.cell_size, overlay)

        # Draw slow effect indicator if active
        if hasattr(self, 'slow_effect_active') and self.slow_effect_active:
            qp.setPen(QColor(0, 120, 255))  # Light blue
            qp.setFont(QFont('Courier', 14))
            slow_text = "SLOW EFFECT ACTIVE"
            text_width = qp.fontMetrics().width(slow_text)
            text_x = round((self.width * cell_size_x - text_width) / 2)
            qp.drawText(text_x, 50, slow_text)

        qp.end()

    def get_rotated_image(self, image, direction):
        """Rotate image based on direction"""
        transform = QTransform()
        
        # Calculate rotation center
        center = image.rect().center()
        transform.translate(center.x(), center.y())
        
        # Set rotation angle based on direction
        if direction == (1, 0):      # Right
            angle = 90
        elif direction == (-1, 0):   # Left
            angle = 270
        elif direction == (0, -1):   # Up
            angle = 0
        else:                        # Down
            angle = 180
        
        transform.rotate(angle)
        transform.translate(-center.x(), -center.y())
        
        return image.transformed(transform, Qt.SmoothTransformation)

    def toggle_golden_apple_glow(self):
        if self.golden_apple_active:
            self.golden_apple_glow = not self.golden_apple_glow
            self.update()

    def golden_apple_countdown(self):
        """Countdown timer for golden apple"""
        self.golden_apple_current_time -= 1
        if self.golden_apple_current_time <= 0:
            self.golden_apple_active = False
            self.golden_apple_timer.stop()
        self.update()

    def toggle_high_score_blink(self):
        """Toggle high score blink state"""
        self.high_score_blink = not self.high_score_blink
        self.update()

    def update_score_animation(self):
        """Update score animation counter"""
        self.score_animation += 1
        if self.score_animation > 20:  # Animation duration
            self.score_animation = 0
            self.score_animation_timer.stop()
        self.update()

    def update_game(self):
        if self.game_over:
            return
        
        head = self.snake[0]
        new_x = (head[0] + self.direction[0]) % self.width
        new_y = (head[1] + self.direction[1]) % self.height
        new_head = (new_x, new_y)
        
        # Debug collision detection
        print(f"Head position: {new_head}")
        if hasattr(self, 'red_crystal_positions'):
            print(f"Red crystal positions: {self.red_crystal_positions}")
        
        # Check for collision with snake body or boulders
        if (new_head in self.snake[1:] or 
            any(new_head in boulder_cells for boulder_cells, _ in self.boulders)):
            self.game_over_handler()
            return
        
        self.snake.insert(0, new_head)
        
        # Check if green crystal eaten
        green_crystal_eaten = False
        if new_head == self.food:
            green_crystal_eaten = True
            print("Green crystal eaten!")
        
        # Check if red crystal eaten - only in mission mode
        red_crystal_eaten = False
        red_crystal_index = None
        
        if hasattr(self, 'in_mission_mode') and self.in_mission_mode and hasattr(self, 'red_crystal_positions'):
            # Debug collision detection with red crystals
            for i, pos in enumerate(self.red_crystal_positions):
                print(f"Checking red crystal {i} at {pos}, head at {new_head}")
                if new_head[0] == pos[0] and new_head[1] == pos[1]:  # Use explicit comparison
                    red_crystal_eaten = True
                    red_crystal_index = i
                    print(f"RED CRYSTAL EATEN at position {pos}!")
                    break
        
        if green_crystal_eaten:
            # Handle green crystal eaten
            self.crystals_collected += 1
            self.score += 1
            
            # Check if we should spawn red crystals at this milestone
            self.spawn_red_crystals()
            
            # Create new green crystal
            self.food = self.create_food()
        
        elif red_crystal_eaten:
            # Apply slow effect - with explicit debug
            print("APPLYING SLOW EFFECT")
            
            # Store original speed
            self.original_speed = self.timer.interval()
            print(f"Original speed (interval): {self.original_speed}ms")
            
            # Set new slower speed
            new_speed = int(self.original_speed * 1.67)  # 40% slower
            print(f"New slower speed (interval): {new_speed}ms")
            self.timer.setInterval(new_speed)
            
            # Set slow effect status
            self.slow_effect_active = True
            
            # Start timer to end slow effect
            if hasattr(self, 'slow_timer'):
                self.slow_timer.stop()  # Stop existing timer if any
            
            self.slow_timer = QTimer()
            self.slow_timer.timeout.connect(self.end_slow_effect)
            self.slow_timer.setSingleShot(True)
            self.slow_timer.start(5000)  # 5 seconds
            
            # Remove eaten crystal
            if red_crystal_index is not None:
                self.red_crystals_eaten.add(self.red_crystal_positions[red_crystal_index])
                self.red_crystal_positions.pop(red_crystal_index)
            
            # Update score
            self.score += 1
        else:
            # No crystal eaten, remove the last segment
            self.snake.pop()
        
        self.update()

    def reset_game(self):
        """Reset the game state"""
        # Hide pause overlay and reset pause state
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            self.pause_overlay.setVisible(False)
        self.paused = False
        
        self.snake = [(self.width//2, self.height//2)]
        self.direction = (1, 0)
        
        # Only clear boulders if not in mission mode
        # For mission mode, boulders are cleared in start_mission_game
        if not hasattr(self, 'in_mission_mode') or not self.in_mission_mode:
            self.boulders = []
        
        self.food = self.create_food()
        self.score = 0
        self.game_over = False
        self.new_high_score = False
        
        # Stop animations
        self.celebration_movie.stop()
        self.high_score_blink_timer.stop()
        self.score_animation_timer.stop()
        self.score_animation = 0
        
        # Make sure game timer is running
        if not self.timer.isActive():
            self.timer.start(100)

    def keyPressEvent(self, event):
        """Handle key press events"""
        # Handle ESC key based on current screen/state
        if event.key() == Qt.Key_Escape:
            # In mission intro screen - go back to campaign menu
            if self.in_mission_intro:
                self.show_campaign_menu()
                return
            
            # In campaign menu - go back to game mode menu
            elif self.in_campaign_menu:
                self.show_game_mode_menu()
                return
            
            # In game mode menu - go back to main menu
            elif self.in_game_mode_menu:
                self.show_main_menu()
                return
            
            # In settings menu - go back to main menu
            elif self.in_settings:
                self.show_main_menu()
                return
            
            # In active game - toggle pause
            elif not self.game_over and not self.in_main_menu:
                self.toggle_pause()
                return
            
            # In game over screen - go to main menu
            elif self.game_over:
                self.show_main_menu()
                return
        
        # If game over, also accept R to restart
        if self.game_over:
            if event.key() == Qt.Key_R:
                # In mission mode, restart the mission
                if hasattr(self, 'in_mission_mode') and self.in_mission_mode:
                    self.reset_mission()
                else:
                    self.reset_game()
                return
            else:
                # For mission complete, any key returns to menu
                if hasattr(self, 'mission_completed') and self.mission_completed:
                    self.mission_completed = False
                    self.show_main_menu()
                    return
                # For other game over states, ignore other keys
                return
        
        # If game is paused or we're in a menu, don't process movement keys
        if self.paused or self.in_main_menu or self.in_settings or self.in_game_mode_menu or self.in_campaign_menu or self.in_mission_intro:
            return
        
        # Process directional keys for snake movement
        if event.key() == Qt.Key_Up or event.key() == Qt.Key_W:
            if self.direction != (0, 1):  # Not moving down
                self.direction = (0, -1)
        elif event.key() == Qt.Key_Down or event.key() == Qt.Key_S:
            if self.direction != (0, -1):  # Not moving up
                self.direction = (0, 1)
        elif event.key() == Qt.Key_Left or event.key() == Qt.Key_A:
            if self.direction != (1, 0):  # Not moving right
                self.direction = (-1, 0)
        elif event.key() == Qt.Key_Right or event.key() == Qt.Key_D:
            if self.direction != (-1, 0):  # Not moving left
                self.direction = (1, 0)

    def toggle_pause(self):
        """Toggle the game's paused state"""
        if self.in_main_menu or self.in_settings or self.in_game_mode_menu or self.game_over:
            return  # Don't pause when in menus or game over
        
        self.paused = not self.paused
        
        if self.paused:
            self.timer.stop()
            # Also pause mission timer if active
            if hasattr(self, 'mission_timer') and self.mission_timer.isActive():
                self.mission_timer.stop()
            # Show pause overlay
            self.pause_overlay.setGeometry(0, 0, self.size().width(), self.size().height())
            self.pause_overlay.setVisible(True)
            self.pause_overlay.raise_()
        else:
            self.timer.start()
            # Resume mission timer if in mission mode
            if hasattr(self, 'in_mission_mode') and self.in_mission_mode:
                self.mission_timer.start(1000)
            # Hide pause overlay
            self.pause_overlay.setVisible(False)

    def resizeEvent(self, event):
        """Handle window resize events"""
        super().resizeEvent(event)
        
        # Update pause overlay size if it exists
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            # Use size() method instead of width()/height() to avoid conflict with instance variables
            self.pause_overlay.setGeometry(0, 0, self.size().width(), self.size().height())
        
        # Make sure container fills the entire available space
        self.container.setFixedSize(self.size().width(), self.size().height())

    def play_apple_sound(self, is_golden=False):
        """Play sound when apple is eaten"""
        if not self.sound_enabled:
            return
            
        if is_golden:
            self.sound_player.setMedia(self.golden_apple_sound)
        else:
            self.sound_player.setMedia(self.apple_sound)
        
        self.sound_player.setVolume(30)  # 30% volume
        self.sound_player.play()
        
        # Stop sound after 0.5 seconds
        self.sound_timer.start(500)

    def stop_sound(self):
        """Stop the current sound effect"""
        self.sound_player.stop()

    def game_over_handler(self):
        """Handle game over state"""
        # Stop all game timers
        self.timer.stop()
        self.golden_apple_timer.stop()
        
        # Stop oxygen warning timer and sounds
        if hasattr(self, 'oxygen_warning_timer'):
            self.oxygen_warning_timer.stop()
            self.oxygen_warning_active = False
            self.sound_player.stop()  # Stop any playing sounds
        
        # Update high score
        self.update_high_score()
        
        # Flag for animation
        self.new_high_score = (self.score == self.high_score and self.score > 0)
        
        # Start high score blinking if we have a new high score
        if self.new_high_score:
            self.high_score_blink_timer.start()
        
        # Set game over flag
        self.game_over = True
        
        # Force redraw
        self.update()
        
        # Save high score to file
        self.save_high_score()

    def _check_audio_ready(self):
        """Check if audio system is ready and restart playback if needed"""
        self.preload_attempts += 1
        
        # Stop preloading after 10 attempts or if we've played for 100ms
        if self.preload_attempts >= 10:
            self.sound_player.stop()
            self.sound_player.setVolume(100)
            self.preload_timer.stop()
            return
        
        # If media player state indicates issues, try again
        if self.sound_player.state() == QMediaPlayer.StoppedState:
            self.sound_player.play()

    def setup_pause_overlay(self):
        """Setup the pause overlay with resume and return to menu buttons"""
        self.pause_overlay = QWidget(self)
        self.pause_overlay.setVisible(False)
        
        # Semi-transparent dark background
        self.pause_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 180);")
        
        # Layout for pause menu
        pause_layout = QVBoxLayout(self.pause_overlay)
        
        # Add spacer at the top
        pause_layout.addStretch(2)
        
        # Pause title
        pause_title = QLabel("PAUSED", self.pause_overlay)
        pause_title.setFont(QFont("Courier", 24, QFont.Bold))
        pause_title.setStyleSheet("color: #00FF00; background-color: transparent;")
        pause_title.setAlignment(Qt.AlignCenter)
        pause_layout.addWidget(pause_title)
        
        pause_layout.addSpacing(40)
        
        # Common button style
        button_style = """
            QPushButton {
                background-color: #005500;
                color: #00FF00;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #007700;
            }
            QPushButton:pressed {
                background-color: #009900;
            }
        """
        
        # Resume button
        resume_button = HoverButton("Resume", self, self.sound_player, lambda: self.sound_enabled)
        resume_button.set_hover_sound(self.hover_sound)
        resume_button.setFixedSize(200, 50)
        resume_button.setFont(QFont("Courier", 16))
        resume_button.setStyleSheet(button_style)
        resume_button.clicked.connect(self.toggle_pause)
        pause_layout.addWidget(resume_button, 0, Qt.AlignHCenter)
        
        pause_layout.addSpacing(20)
        
        # Menu button (only one)
        menu_button = HoverButton("Menu", self, self.sound_player, lambda: self.sound_enabled)
        menu_button.set_hover_sound(self.hover_sound)
        menu_button.setFixedSize(200, 50)
        menu_button.setFont(QFont("Courier", 16))
        menu_button.setStyleSheet(button_style)
        menu_button.clicked.connect(self.show_main_menu)
        pause_layout.addWidget(menu_button, 0, Qt.AlignHCenter)
        
        # Add spacer at the bottom
        pause_layout.addStretch(2)

    def setup_game_mode_menu(self):
        """Setup the game mode selection menu"""
        # Create a widget for the game mode menu
        self.game_mode_widget = QWidget()
        
        # Set a solid dark green background
        self.game_mode_widget.setStyleSheet("background-color: #003300;")
        
        # Create a layout for the menu
        layout = QVBoxLayout()
        
        # Add spacer at the top to push buttons down
        layout.addStretch()
        
        # Add a title
        title_label = QLabel("Select Game Mode", self)
        title_label.setFont(QFont("Courier", 24, QFont.Bold))
        title_label.setStyleSheet("color: #00FF00;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addSpacing(40)
        
        # Common button style - same as main menu
        button_style = """
            QPushButton {
                background-color: #005500;
                color: #00FF00;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #007700;
            }
            QPushButton:pressed {
                background-color: #009900;
            }
        """
        
        # Create and add the buttons with hover sound
        self.casual_button = HoverButton("Casual", self, self.sound_player, lambda: self.sound_enabled)
        self.casual_button.set_hover_sound(self.hover_sound)
        self.casual_button.setFixedSize(200, 50)
        self.casual_button.setFont(QFont("Courier", 16))
        self.casual_button.setStyleSheet(button_style)
        self.casual_button.clicked.connect(self.start_casual_game)
        layout.addWidget(self.casual_button, 0, Qt.AlignHCenter)
        
        # Add spacing between buttons
        layout.addSpacing(20)
        
        # Create Campaign button
        self.campaign_button = HoverButton("Campaign", self, self.sound_player, lambda: self.sound_enabled)
        self.campaign_button.set_hover_sound(self.hover_sound)
        self.campaign_button.setFixedSize(200, 50)
        self.campaign_button.setFont(QFont("Courier", 16))
        self.campaign_button.setStyleSheet(button_style)
        self.campaign_button.clicked.connect(self.start_campaign_game)
        layout.addWidget(self.campaign_button, 0, Qt.AlignHCenter)
        
        # Add spacing between buttons
        layout.addSpacing(20)
        
        # Create Back button
        self.back_button = HoverButton("Back", self, self.sound_player, lambda: self.sound_enabled)
        self.back_button.set_hover_sound(self.hover_sound)
        self.back_button.setFixedSize(200, 50)
        self.back_button.setFont(QFont("Courier", 16))
        self.back_button.setStyleSheet(button_style)
        self.back_button.clicked.connect(self.show_main_menu)
        layout.addWidget(self.back_button, 0, Qt.AlignHCenter)
        
        # Add spacer at the bottom
        layout.addStretch()
        
        # Set the layout
        self.game_mode_widget.setLayout(layout)

    def setup_campaign_menu(self):
        """Setup the campaign level selection menu"""
        # Create a widget for the campaign menu
        self.campaign_widget = QWidget()
        
        # Use a simple solid background color instead of image
        self.campaign_widget.setStyleSheet("background-color: #220011;")
        
        # Create a layout for the menu
        layout = QVBoxLayout()
        
        # Add spacer at the top to push content down
        layout.addStretch(1)
        
        # Create grid layout for level selection
        level_grid = QGridLayout()
        level_grid.setSpacing(15)  # Spacing between level boxes
        
        # Active level style (reddish-brown)
        active_style = """
            background-color: #772200;
            color: #FF8800;
            border: none;
            border-radius: 10px;
            font-weight: bold;
        """
        
        # Locked level style (dark gray)
        locked_style = """
            background-color: #333333;
            color: #888888;
            border: none;
            border-radius: 10px;
        """
        
        # Create level boxes (first one active, others locked)
        rows, cols = 2, 3  # 2 rows, 3 columns for 6 levels
        
        for level in range(1, 7):
            # Create level box
            level_box = QPushButton(str(level), self)
            level_box.setFixedSize(100, 100)  # Square boxes
            level_box.setFont(QFont("Courier", 24, QFont.Bold))
            
            if level == 1:  # First level is active
                level_box.setStyleSheet(active_style)
                level_box.setEnabled(True)
                level_box.clicked.connect(self.show_mission_intro)
            else:  # Other levels are locked
                level_box.setStyleSheet(locked_style)
                level_box.setEnabled(False)
            
            # Add to grid (calculate row and column)
            row = (level - 1) // cols
            col = (level - 1) % cols
            level_grid.addWidget(level_box, row, col)
        
        # Add the grid to the main layout with horizontal centering
        grid_container = QWidget()
        grid_container.setLayout(level_grid)
        grid_container.setStyleSheet("background: transparent;")
        layout.addWidget(grid_container, 0, Qt.AlignHCenter)
        
        layout.addSpacing(50)
        
        # Back button (reddish-brown like active level)
        back_button = HoverButton("Back", self, self.sound_player, lambda: self.sound_enabled)
        back_button.set_hover_sound(self.hover_sound)
        back_button.setFixedSize(200, 60)
        back_button.setFont(QFont("Courier", 18, QFont.Bold))
        back_button.setStyleSheet("""
            background-color: #772200;
            color: #FF8800;
            border: none;
            border-radius: 10px;
            padding: 10px;
        """)
        back_button.clicked.connect(self.show_game_mode_menu)
        layout.addWidget(back_button, 0, Qt.AlignHCenter)
        
        # Add spacer at the bottom
        layout.addStretch(1)
        
        # Set the layout
        self.campaign_widget.setLayout(layout)

    def show_mission_intro(self):
        """Show mission 1 intro screen with background and story"""
        # Stop any running game timers
        if self.timer.isActive():
            self.timer.stop()
        
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Create widget for mission intro
        mission_widget = QWidget()
        
        # Enable automatic background filling
        mission_widget.setAutoFillBackground(True)
        
        # Using raw string for the path
        image_path = r"D:\Work\Personal\Programming\Game\Snake\asset\mission\mission 1\mission1_background.png"
        
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print("Failed to load image")
            # Create checkerboard pattern with the requested colors for the first mission
            mission_widget.setStyleSheet("""
                background-color: #780000;
                background-image: linear-gradient(45deg, #c1121f 25%, transparent 25%),
                                  linear-gradient(-45deg, #c1121f 25%, transparent 25%),
                                  linear-gradient(45deg, transparent 75%, #c1121f 75%),
                                  linear-gradient(-45deg, transparent 75%, #c1121f 75%);
                background-size: 60px 60px;
                background-position: 0 0, 0 30px, 30px -30px, -30px 0px;
            """)
        else:
            # Use image as background
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pixmap.scaled(
                self.width * self.cell_size,
                self.height * self.cell_size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )))
            mission_widget.setPalette(palette)
        
        # Create layout for mission intro
        mission_layout = QVBoxLayout(mission_widget)
        mission_layout.addSpacing(20)
        
        # Title with golden color
        title_label = QLabel("Mission 1: The Awakening", self)
        title_label.setFont(QFont("Courier", 30, QFont.Bold))
        title_label.setStyleSheet("color: #FFCC00;")
        title_label.setAlignment(Qt.AlignCenter)
        mission_layout.addWidget(title_label)
        
        # Add space after title
        mission_layout.addSpacing(10)
        
        # Create story text with better formatting for 720p
        story_text = QLabel()
        story_text.setWordWrap(True)
        story_text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        story_text.setStyleSheet("""
            color: #00FF00;
            background-color: rgba(0, 0, 0, 180);
            padding: 40px;
            border-radius: 15px;
            font-family: Courier;
            font-size: 15px;
        """)
        
        # Use text formatting with HTML to make it more readable
        story_html = """
        <p><span style='color:#FFCC00; font-size:19px; font-weight:bold;'>Zeta Galaxy, a desolate planet called Xyra-9...</span></p>
        <p>The cosmic serpent Nova awoke, its glowing eyes scanning the alien terrain. Its memory was blank—only a faint voice echoed in its mind:</p>
        <p><span style='color:#AAAAFF; font-style:italic; font-size:15px;'>"Wake up... You are the last survivor..."</span></p>
        <p>Beneath Nova lay a surface of celestial rocks, shimmering in hues of red and blue. Scattered across the land were crystals pulsating with an unknown energy. Yet, some of them emitted a strange red glow...</p>
        <p><span style='color:#FF0000; font-size:17px; font-weight:bold;'>WARNING: Oxygen levels at 80% and dropping!</span></p>
        <p><span style='color:#FFCC00; font-size:19px; font-weight:bold;'>Mission:</span></p>
        <ul>
        <li>Collect the green crystals to restore energy and strengthen your body.</li>
        <li>Avoid the red crystals! They are toxic and will weaken you for a short time.</li>
        <li>Navigate through the alien cliffs and uncover the truth that awaits you...</li>
        </ul>
        """
        
        story_text.setText(story_html)
        story_text.setMinimumHeight(600)  # Increased height for 720p
        mission_layout.addWidget(story_text, 1)
        
        mission_layout.addSpacing(20)
        
        # Next button with brown/orange styling
        next_button = HoverButton("Next", self, self.sound_player, lambda: self.sound_enabled)
        next_button.set_hover_sound(self.hover_sound)
        next_button.setFixedSize(300, 70)
        next_button.setFont(QFont("Courier", 24, QFont.Bold))
        next_button.setStyleSheet("""
            background-color: #780000;
            color: #ff8800;
            border: none;
            border-radius: 15px;
            padding: 15px;
        """)
        next_button.clicked.connect(self.start_mission_game)
        mission_layout.addWidget(next_button, 0, Qt.AlignHCenter)
        
        mission_layout.addSpacing(10)
        
        # Add and show mission intro
        self.container_layout.addWidget(mission_widget)
        mission_widget.show()
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = False
        self.in_mission_intro = True
        self.paused = True
        
        # Make sure game is not running
        self.timer.stop()

    def start_mission_game(self):
        """Start the mission game after intro"""
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Reset game state
        self.reset_game()
        
        # Set mission-specific background colors and elements
        # Store the original colors to restore them later
        self.original_bg_color = self.bg_color
        self.original_grid_color = self.grid_color
        
        # Set the custom checkerboard colors for mission 1
        self.bg_color = QColor("#4f000b")  # Dark red base
        self.grid_color = QColor("#720026")  # Slightly brighter red for pattern
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        self.in_campaign_menu = False
        self.in_mission_intro = False
        self.in_mission_mode = True  # Add this flag to track if we're in mission mode
        self.current_mission = 1     # Track which mission we're in
        
        # Initialize crystal count for mission
        self.crystals_collected = 0
        self.crystals_required = 20  # Need 20 crystals to complete mission 1
        
        # Clear all boulders and make sure they won't appear
        self.boulders = []
        self.boulder_count = 0
        self.obstacles_enabled = False
        
        # Reset and start oxygen depletion
        self.oxygen_level = 80  # Start with 80% oxygen
        self.mission_timer.start(1000)  # Update every 1000ms (1 second)
        
        # Create new food without boulders
        self.food = self.create_food()
        
        # Start the game timer
        self.paused = False
        self.timer.start(122)  # Slightly slower for mission 1
        
        # Set focus to the game
        self.setFocus()

    def update_oxygen_level(self):
        """Update oxygen level and handle low oxygen warnings"""
        # Reduce oxygen by a small amount each time
        oxygen_depletion_per_second = 100 / self.oxygen_depletion_time
        self.oxygen_level -= oxygen_depletion_per_second
        
        # Ensure oxygen doesn't go below 0
        if self.oxygen_level < 0:
            self.oxygen_level = 0
        
        # Check if oxygen is below 30% threshold
        if self.oxygen_level < 30 and not self.oxygen_warning_active:
            # Start oxygen warning
            self.oxygen_warning_active = True
            self.oxygen_warning_timer.start()
            self.play_oxygen_warning()  # Play immediately on first detection
            print("Oxygen low! Warning activated.")
        
        # Check if oxygen is above 30% threshold and warnings are active
        elif self.oxygen_level >= 30 and self.oxygen_warning_active:
            # Stop oxygen warnings
            self.oxygen_warning_active = False
            self.oxygen_warning_timer.stop()
            print("Oxygen restored to safe levels. Warning deactivated.")
        
        # Force a redraw to update the oxygen display
        self.update()
        
        # If oxygen runs out, game over
        if self.oxygen_level <= 0:
            self.game_over_handler()

    def play_oxygen_warning(self):
        """Play the oxygen warning sound"""
        if self.sound_enabled and self.oxygen_warning_active:
            print("Playing oxygen warning sound!")
            self.sound_player.setMedia(self.oxygen_warning_sound)
            self.sound_player.setVolume(40)  # Set to 40% volume
            self.sound_player.play()

    def mission_failed(self):
        """Handle mission failure due to oxygen depletion"""
        self.game_over = True
        self.timer.stop()
        
        # Special flag for mission failure
        self.mission_failed_flag = True
        self.mission_completed = False
        
        self.update()

    def mission_complete(self):
        """Handle mission completion"""
        self.game_over = True
        self.timer.stop()
        
        # Stop the mission timer
        self.mission_timer.stop()
        
        # We'll show a special completion screen
        self.mission_completed = True
        self.mission_failed_flag = False
        
        self.update()

    def reset_mission(self):
        """Reset just the mission without going back to menu"""
        # Hide pause overlay and reset pause state
        if hasattr(self, 'pause_overlay') and self.pause_overlay:
            self.pause_overlay.setVisible(False)
        self.paused = False
        
        # Reset snake
        self.snake = [(self.width//2, self.height//2)]
        self.direction = (1, 0)
        
        # Clear mission-specific flags
        self.mission_failed_flag = False
        self.mission_completed = False
        
        # Reset crystal counts
        self.crystals_collected = 0
        
        # Reset and restart the mission timer
        self.mission_time_remaining = 120
        self.mission_timer.start(1000)
        
        # New food
        self.food = self.create_food()
        self.score = 0
        self.game_over = False
        
        # Make sure game timer is running
        if not self.timer.isActive():
            self.timer.start(100)

    def end_slow_effect(self):
        """End the slow effect and restore normal speed"""
        # Only restore if the effect is active
        if self.slow_effect_active:
            # Restore original speed
            self.timer.setInterval(self.original_speed)
            
            # Reset slow effect status
            self.slow_effect_active = False
            
            print("Slow effect ended, speed restored to normal")

    def spawn_red_crystals(self):
        """Spawn red crystals at certain milestones"""
        # Skip if not in mission mode
        if not hasattr(self, 'in_mission_mode') or not self.in_mission_mode:
            return
        
        # Check if we've reached a milestone for spawning red crystals
        milestones = [0, 2, 5, 10, 15]
        
        if self.crystals_collected in milestones:
            print(f"MILESTONE REACHED: {self.crystals_collected} crystals - spawning red crystals")
            
            # Determine how many red crystals to spawn
            num_to_spawn = 2  # Base 2 red crystals per milestone
            
            # Create the specified number of red crystals
            for _ in range(num_to_spawn):
                self.spawn_single_red_crystal()

    def draw_red_crystals(self, qp, cell_size_x, cell_size_y):
        """Draw red crystals on the game board"""
        # Skip if not in mission mode
        if not hasattr(self, 'in_mission_mode') or not self.in_mission_mode:
            return
        
        # Draw each red crystal
        if hasattr(self, 'red_crystal_positions'):
            for pos in self.red_crystal_positions:
                x = round(pos[0] * cell_size_x)
                y = round(pos[1] * cell_size_y)
                
                # Draw the red crystal image if it exists
                if 'red_crystal' in self.mission_images and not self.mission_images['red_crystal'].isNull():
                    crystal_width = round(cell_size_x)
                    crystal_height = round(cell_size_y)
                    
                    red_crystal_img = self.mission_images['red_crystal'].scaled(
                        crystal_width, crystal_height,
                        Qt.IgnoreAspectRatio, Qt.SmoothTransformation
                    )
                    qp.drawImage(x, y, red_crystal_img)

    def initialize_red_crystals(self):
        """Generate initial two red crystals at random positions"""
        print("Initializing first two red crystals at game start")
        
        # Generate 2 random positions for initial red crystals
        initial_positions = []
        attempts = 0
        
        # Try to find good positions (not on snake or green crystal)
        while len(initial_positions) < 2 and attempts < 50:
            attempts += 1
            
            # Generate random position
            x = random.randint(2, self.width - 3)  # Stay away from edges
            y = random.randint(2, self.height - 3)
            pos = (x, y)
            
            # Check if position is valid (not on snake, not on green crystal)
            if (pos not in self.snake and 
                pos != self.food and 
                pos not in initial_positions):
                
                initial_positions.append(pos)
                print(f"Added initial red crystal at {pos}")
        
        # Set these as our red crystal positions
        self.red_crystal_positions = initial_positions
        print(f"Initial red crystal positions: {self.red_crystal_positions}")

    def spawn_single_red_crystal(self):
        """Generate a single red crystal at a random position"""
        # Generate a random position that is not on the snake or the food
        while True:
            x = random.randint(2, self.width - 3)  # Stay away from edges
            y = random.randint(2, self.height - 3)
            pos = (x, y)
            if pos not in self.snake and pos != self.food:
                self.red_crystal_positions.append(pos)
                print(f"Added new red crystal at {pos}")
                break

    def start_normal_game(self):
        """Start normal (score-based) game mode"""
        # Hide all widgets first
        for i in reversed(range(self.container_layout.count())): 
            widget = self.container_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                self.container_layout.removeWidget(widget)
        
        # Reset game state
        self.reset_game()
        
        # Make sure we're not in mission mode
        self.in_mission_mode = False
        
        # Clear red crystals specifically for normal mode
        self.red_crystal_positions = []
        
        # Update state flags
        self.in_main_menu = False
        self.in_settings = False
        self.in_game_mode_menu = False
        
        # Start the game timer
        self.paused = False
        self.timer.start(100)  # Adjust speed as needed
        
        # Set focus to the game
        self.setFocus()

class HoverButton(QPushButton):
    def __init__(self, text, parent=None, sound_player=None, sound_enabled_func=None):
        super().__init__(text, parent)
        self.sound_player = sound_player
        self.sound_enabled_func = sound_enabled_func
        self.hover_sound = None
        self.sound_timer = parent.sound_timer if parent else None
        
    def set_hover_sound(self, sound):
        self.hover_sound = sound
        
    def enterEvent(self, event):
        # Play hover sound if enabled
        if (self.sound_player and self.hover_sound and 
            self.sound_enabled_func and self.sound_enabled_func()):
            self.sound_player.setMedia(self.hover_sound)
            self.sound_player.setVolume(30)  # 30% volume
            self.sound_player.play()
            
            # Stop sound after 0.5 seconds if timer exists
            if self.sound_timer:
                self.sound_timer.start(500)
                
        super().enterEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    game = SnakeGame()
    sys.exit(app.exec_()) 