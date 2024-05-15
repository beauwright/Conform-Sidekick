use tauri::{CustomMenuItem, Menu, MenuItem, Submenu};

fn main() {
    let help = CustomMenuItem::new("help".to_string(), "About");

    let help_submenu = Submenu::new("Help", Menu::new().add_item(help));
    let app_submenu = Submenu::new(
        "Conform Sidekick",
        Menu::new()
            .add_native_item(MenuItem::Hide)
            .add_native_item(MenuItem::Separator)
            .add_native_item(MenuItem::Quit),
    );

    let menu = Menu::new()
        .add_submenu(app_submenu)
        .add_submenu(help_submenu);

    tauri::Builder::default()
        .menu(menu)
        .on_menu_event(|event| {
            match event.menu_item_id() {
                "help" => {
                    event.window().emit("navigate", "licenses").unwrap();
                }
                _ => {}
            }
        })
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
