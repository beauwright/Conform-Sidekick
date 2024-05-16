// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{CustomMenuItem, Menu, MenuItem, Submenu};

fn main() {
    let help = CustomMenuItem::new("help".to_string(), "About");

    let help_submenu = Submenu::new("Help", Menu::new().add_item(help));

    // Define the menu based on the target OS
    #[cfg(target_os = "macos")]
    let menu = build_macos_menu(help_submenu);

    #[cfg(not(target_os = "macos"))]
    let menu = build_windows_menu(help_submenu);

    tauri::Builder::default()
        .menu(menu)
        .on_menu_event(|event| match event.menu_item_id() {
            "help" => {
                event.window().emit("navigate", "licenses").unwrap();
            }
            _ => {}
        })
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// Function to build the menu for macOS
#[cfg(target_os = "macos")]
fn build_macos_menu(help_submenu: Submenu) -> Menu {
    Menu::new()
        .add_submenu(Submenu::new("Conform Sidekick", Menu::new()
            .add_native_item(MenuItem::Hide)
            .add_native_item(MenuItem::Separator)
            .add_native_item(MenuItem::Quit)))
        .add_submenu(help_submenu)
}

// Function to build the menu for other operating systems
#[cfg(not(target_os = "macos"))]
fn build_windows_menu(help_submenu: Submenu) -> Menu {
    Menu::new()
        .add_submenu(Submenu::new("File", Menu::new()
            .add_native_item(MenuItem::Quit)))
        .add_submenu(help_submenu)
}
